"""
chat_service.py
─────────────────────────────────────────────────────────────────────────────
Core Q&A logic combining RAG (retrieval-augmented generation) with
conversation history and intent detection.

Flow for each user message:
  1. Intent detection  — is this a greeting/social message or a real question?
  2. If greeting       → polite response, no RAG needed
  3. If question       → retrieve top-5 chunks from ChromaDB (scoped to leaflet)
  4. Build prompt      → system prompt (strict grounding rules) + history + question
  5. LLM call          → GPT-4o-mini, temperature=0 for deterministic medical answers
  6. Parse response    → extract <answer> and <citations> blocks
  7. Citations enriched with page number and section from chunk metadata

Error handling covers:
  • OpenAI timeout     → ChatbotError(LLM_TIMEOUT)
  • Rate limit (429)   → ChatbotError(LLM_RATE_LIMIT)
  • Any other API err  → ChatbotError(LLM_API_ERROR)
  • Context too long   → ChatbotError(LLM_CONTEXT_TOO_LONG)
"""

import os
import re
import json
import asyncio
from openai import APITimeoutError, RateLimitError, APIError, BadRequestError
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, AIMessage, SystemMessage

from services.chroma_service import query_chunks, leaflet_exists
from errors import ChatbotError, ErrorCode
from observability import get_logger, track_latency, metrics

log = get_logger("chat_service")

# ── Greeting detection ────────────────────────────────────────────────────────
# Matches short social/conversational messages in English and Hebrew that
# should NOT trigger the RAG pipeline.
_GREETING_PATTERNS = re.compile(
    r"^\s*(hi+|hello+|hey+|good\s*(morning|afternoon|evening|day)|shalom|howdy|greetings|what'?s\s*up|thanks?|thank\s*you|bye+|goodbye+|see\s*you|great|awesome|ok+|okay|perfect|got\s*it|understood|שלום|היי+|בוקר\s*טוב|ערב\s*טוב|צהריים\s*טובים|לילה\s*טוב|תודה|תודה\s*רבה|יופי|מעולה|בסדר|אוקיי|נהדר|מצוין|כן|לא|אוקי)\W*$",
    re.IGNORECASE,
)

# ── System prompt (strict medical grounding) ──────────────────────────────────
# This prompt is re-used for every question. The {context} placeholder is
# filled with the retrieved chunks right before the LLM call.
MEDICAL_SYSTEM_PROMPT = """\
You are a medical information assistant. Your ONLY source of truth is the \
medical leaflet content provided in the LEAFLET EXCERPTS section below.

STRICT RULES:
1. Answer based on information present in the LEAFLET EXCERPTS.
2. Look carefully through ALL excerpts — the answer may be spread across multiple chunks.
3. If the excerpts contain ANY relevant information, use it to answer.
   Only say "This information is not available in the provided leaflet."
   if the excerpts contain absolutely nothing relevant.
4. Do NOT add external medical knowledge beyond what is in the leaflet.
5. You may use conversation history to understand follow-up questions,
   but factual answers must be grounded only in the leaflet excerpts.
6. Be concise and accurate. Do not speculate or extrapolate.
7. ALWAYS output citations. Even if the answer seems obvious, you MUST include
   verbatim quotes from the excerpts that support it. Never omit the citations block.
   Each citation MUST include the page number and section if available.

OUTPUT FORMAT - you MUST always use these exact XML tags, no exceptions:
<answer>
[Your answer here]
</answer>
<citations>
[
  {{"text": "exact verbatim quote from leaflet", "page": 3, "section": "Side Effects"}},
  {{"text": "another exact quote", "page": 1, "section": null}}
]
</citations>

Even for follow-up or clarification questions, always output both <answer> and <citations> tags.
If truly no relevant information is found: <answer>This information is not available in the provided leaflet.</answer><citations>[]</citations>

---
LEAFLET EXCERPTS (retrieved for this question):
{context}
"""

# ── Greeting system prompt ────────────────────────────────────────────────────
GREETING_SYSTEM_PROMPT = """\
You are a friendly medical leaflet assistant. The user has greeted you or \
sent a short social message. Respond warmly and briefly (1-2 sentences), \
and remind them that you can answer questions about the medical leaflet \
they uploaded. Do not provide any medical information in this response.
"""


# ── Response parser ───────────────────────────────────────────────────────────

def _parse_response(raw: str) -> dict:
    """
    Extract <answer> and <citations> from the structured LLM output.
    Falls back gracefully if the model doesn't follow the format perfectly.
    """
    answer, citations = "", []

    m = re.search(r"<answer>(.*?)</answer>", raw, re.DOTALL)
    if m:
        answer = m.group(1).strip()

    c = re.search(r"<citations>(.*?)</citations>", raw, re.DOTALL)
    if c:
        try:
            parsed = json.loads(c.group(1).strip())
            if isinstance(parsed, list):
                for item in parsed[:3]:
                    if isinstance(item, str):
                        citations.append({"text": item, "page": None, "section": None})
                    elif isinstance(item, dict) and "text" in item:
                        citations.append({
                            "text":    item["text"],
                            "page":    item.get("page"),
                            "section": item.get("section"),
                        })
        except (json.JSONDecodeError, ValueError):
            pass

    # If no <answer> tag was found, strip any XML tags from the raw response
    # so we never leak <citations>[...]</citations> into the displayed answer
    if not answer:
        clean = re.sub(r"<(answer|citations)>.*?</\1>", "", raw, flags=re.DOTALL).strip()
        answer = clean or raw.strip()

    return {"answer": answer, "citations": citations}


# ── History builder ───────────────────────────────────────────────────────────

def _build_history(history: list[dict]) -> list:
    """Convert stored DB message history to LangChain message objects."""
    messages = []
    for m in history:
        if m["role"] == "user":
            messages.append(HumanMessage(content=m["content"]))
        else:
            # Strip XML tags from prior assistant messages so history is clean
            clean = re.sub(r"<(answer|citations)>.*?</\1>", "", m["content"], flags=re.DOTALL).strip()
            messages.append(AIMessage(content=clean or m["content"]))
    return messages


# ── LLM factory ──────────────────────────────────────────────────────────────

def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,           # deterministic — important for medical answers
        request_timeout=30,      # hard timeout per request
        max_retries=2,           # automatic retry on transient failures
        openai_api_key=os.getenv("OPENAI_API_KEY"),
    )


# ── OpenAI error mapper ───────────────────────────────────────────────────────

def _map_openai_error(exc: Exception) -> ChatbotError:
    """Map OpenAI SDK exceptions to our structured ChatbotError types."""
    if isinstance(exc, APITimeoutError) or isinstance(exc, asyncio.TimeoutError):
        return ChatbotError(ErrorCode.LLM_TIMEOUT, detail=str(exc))
    if isinstance(exc, RateLimitError):
        return ChatbotError(ErrorCode.LLM_RATE_LIMIT, detail=str(exc))
    if isinstance(exc, BadRequestError) and "context_length_exceeded" in str(exc):
        return ChatbotError(ErrorCode.LLM_CONTEXT_TOO_LONG, detail=str(exc))
    if isinstance(exc, APIError):
        return ChatbotError(ErrorCode.LLM_API_ERROR, detail=str(exc))
    return ChatbotError(ErrorCode.INTERNAL_ERROR, detail=str(exc))


# ── Greeting handler ──────────────────────────────────────────────────────────

async def _handle_greeting(question: str) -> dict:
    """
    For social/greeting messages: respond warmly without touching the leaflet.
    No citations returned.
    """
    llm = _get_llm()
    try:
        response = await llm.ainvoke([
            SystemMessage(content=GREETING_SYSTEM_PROMPT),
            HumanMessage(content=question),
        ])
        metrics.record_llm_call(success=True)
        return {"answer": response.content.strip(), "citations": [], "is_greeting": True}
    except Exception as exc:
        metrics.record_llm_call(success=False)
        raise _map_openai_error(exc) from exc


# ── Main entry point ──────────────────────────────────────────────────────────

async def answer_question(
    leaflet_id: str,
    question: str,
    history: list[dict],
    request_id: str = "",
) -> dict:
    """
    Full RAG pipeline for a medical question.

    Args:
        leaflet_id:  ChromaDB scope — only this PDF's chunks are searched
        question:    The user's current message
        history:     Prior [{role, content}] messages in this chat (for context)
        request_id:  For log correlation

    Returns:
        {"answer": str, "citations": [{"text", "page", "section"}], "is_greeting": bool}
    """
    ctx = {"request_id": request_id, "leaflet_id": leaflet_id}

    # ── 1. Intent: greeting or real question? ─────────────────────────────────
    if _GREETING_PATTERNS.match(question.strip()):
        log.info("Greeting detected, skipping RAG", extra=ctx)
        return await _handle_greeting(question)

    # ── 2. Verify leaflet is indexed ──────────────────────────────────────────
    if not leaflet_exists(leaflet_id):
        raise ChatbotError(ErrorCode.LEAFLET_NOT_INDEXED, detail=f"leaflet_id={leaflet_id}")

    # ── 3. Expand query using history for vague follow-up questions ──────────
    # Short/vague follow-ups like "tell me more" or "תוכל להסביר?" have no
    # keywords to match the leaflet. Prepend the last assistant answer so the
    # embedding search gets meaningful medical terms.
    search_query = question
    if history and len(question.strip()) < 60:
        last_assistant = next(
            (m["content"] for m in reversed(history) if m["role"] == "assistant"),
            None,
        )
        if last_assistant:
            clean = re.sub(r"<(answer|citations)>.*?</\1>", "", last_assistant, flags=re.DOTALL).strip()
            search_query = clean + "\n" + question

    # ── 4. Retrieve relevant chunks ───────────────────────────────────────────
    with track_latency(log, "vector_search", ctx):
        relevant = query_chunks(leaflet_id, search_query, n_results=8)

    if not relevant:
        log.info("No relevant chunks found", extra=ctx)
        return {
            "answer": "This information is not available in the provided leaflet.",
            "citations": [],
            "is_greeting": False,
        }

    # ── 4. Build context string with page + section labels ────────────────────
    context_parts = []
    for chunk in relevant:
        label = f"[Page {chunk['page']}"
        if chunk.get("section"):
            label += f" — {chunk['section']}"
        label += "]"
        context_parts.append(f"{label}\n{chunk['text']}")

    context = "\n\n---\n\n".join(context_parts)

    # ── 5. Build message list: system → history → current question ────────────
    messages = [SystemMessage(content=MEDICAL_SYSTEM_PROMPT.format(context=context))]
    messages.extend(_build_history(history))
    messages.append(HumanMessage(content=question))

    # ── 6. LLM call with error handling ──────────────────────────────────────
    llm = _get_llm()
    try:
        with track_latency(log, "llm_call", ctx):
            response = await llm.ainvoke(messages)
        metrics.record_llm_call(success=True)
    except Exception as exc:
        metrics.record_llm_call(success=False)
        raise _map_openai_error(exc) from exc

    # ── 7. Parse and return ───────────────────────────────────────────────────
    result = _parse_response(response.content)
    result["is_greeting"] = False

    log.info(
        "Answer generated",
        extra={
            **ctx,
            "chunks_used":   len(relevant),
            "citations":     len(result["citations"]),
            "answer_length": len(result["answer"]),
        },
    )

    return result