"""
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

# Greeting detection
# Matches short social/conversational messages in English and Hebrew that
# should not trigger the RAG pipeline.
_GREETING_PATTERNS = re.compile(
    r"^\s*(hi+|hello+|hey+|good\s*(morning|afternoon|evening|day)|shalom|howdy|greetings|what'?s\s*up|thanks?|thank\s*you|bye+|goodbye+|see\s*you|great|awesome|ok+|okay|perfect|got\s*it|understood|שלום|היי+|בוקר\s*טוב|ערב\s*טוב|צהריים\s*טובים|לילה\s*טוב|תודה|תודה\s*רבה|יופי|מעולה|בסדר|אוקיי|נהדר|מצוין|כן|לא|אוקי|מה\s*קורה|מה\s*נשמע|מה\s*המצב|מה\s*חדש|מה\s*העניינים|מה\s*איתך|איך\s*אתה|איך\s*את|איך\s*הולך|הכל\s*בסדר)\W*$",
    re.IGNORECASE,
)

# System prompt (strict medical grounding) 
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
6. Be concise and accurate. Do not speculate or extrapolate. Answer only what was asked, nothing more.
7. Do NOT add any polite closing phrases, introductions, or extra commentary. Answer directly.
8. ALWAYS output citations — this is MANDATORY for every single response without exception.
   You MUST include verbatim quotes from the excerpts that support your answer.
   Never omit the citations block, even for simple or obvious answers.
   Each citation MUST be a direct quote from the excerpts, with page number.
   If you cannot find a supporting quote, use the closest relevant text from the excerpts as one.
9. NEVER include citations or page references inside the <answer> text. All citations MUST be in the <citations> block only.

OUTPUT FORMAT - you MUST always use these exact XML tags, no exceptions:
<answer>
[Your answer here - NO inline citations, NO (page X), no citations inside the answer text.]
</answer>
<citations>
[
  {{"text": "exact verbatim quote from leaflet", "page": 3, "section": "Side Effects"}},
  {{"text": "another exact quote", "page": 1, "section": null}}
]
</citations>

CRITICAL FORMATTING RULES:
- The <answer> block must contain ONLY the answer text — no citations, no page references, no "(עמוד X)", no "ציטוט:"
- All citations go EXCLUSIVELY in the <citations> JSON array
- Do NOT write citations inline in the answer text
- Do NOT write (עמוד X) inside the answer
- Do NOT write "ציטוט:" or "מקורות:" inside the answer

EXAMPLE of correct output:
<answer>
Some medical information based on the leaflet content.
</answer>
<citations>
[
  {{"text": "Exact citation from leaflet", "page": 6, "section": "example section"}},
  {{"text": "Another relevant quote", "page": 2, "section": null}}
]
</citations>

EXAMPLE of WRONG output (never do this):
<answer>
Some medical information based on the leaflet content. As stated on page 6, 'Exact citation from leaflet'.
</answer>

Even for follow-up or clarification questions, always output both <answer> and <citations> tags.
If truly no relevant information is found: <answer>This information is not available in the provided leaflet.</answer><citations>[]</citations>

IMPORTANT REMINDER: Citations are MANDATORY for EVERY answer. If you provide an answer, you MUST include at least one citation from the excerpts in the <citations> block. Do not skip this step.
CRITICAL: NEVER put citations or quotes inside the <answer> text. All citations MUST be in the <citations> block ONLY. If you put quotes in the answer, the response will be invalid and rejected.

Repeat the output format:
<answer>
[Your answer here - NO inline citations, NO quotes, no page references.]
</answer>
<citations>
[
  {{"text": "exact verbatim quote from leaflet", "page": 3, "section": "Side Effects"}},
  {{"text": "another exact quote", "page": 1, "section": null}}
]
</citations>

---
LEAFLET EXCERPTS (retrieved for this question):
{context}
"""

# Greeting system prompt 
GREETING_SYSTEM_PROMPT = """\
You are a friendly medical leaflet assistant. The user has greeted you or \
sent a short social message. Respond warmly and briefly (1-2 sentences), \
and remind them that you can answer questions about the medical leaflet \
they uploaded. Do not provide any medical information in this response.
"""

# Response parser 

def _parse_response(raw: str, context: str = "") -> dict:
    """
    Extract <answer> and <citations> from the structured LLM output.
    Falls back gracefully if the model doesn't follow the format perfectly.
    If no citations block, extract inline quotes from answer and match to context for pages.
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
    
    # safety strip
    answer = re.sub(r"</?(answer|citations)>", "", answer).strip()

    # Post-process: remove any inline citations from answer (e.g., (עמוד X))
    answer = re.sub(r'\s*\(עמוד\s*\d+\)', '', answer).strip()
    answer = re.sub(r'\s*\(page\s*\d+\)', '', answer, re.IGNORECASE).strip()

    # Fallback: if no citations from block, extract inline quotes from answer
    if not citations and context:
        # Find quoted strings in answer, e.g., "text"
        inline_quotes = re.findall(r'"([^"]*)"', answer)
        for quote in inline_quotes[:3]:  # Limit to 3
            # Find the best matching chunk in context based on word overlap
            lines = context.split('\n\n---\n\n')
            best_match = None
            best_score = 0
            quote_words = set(re.findall(r'\w+', quote))  # Split into words
            for line in lines:
                # Extract text part after the label
                parts = line.split('\n', 1)
                if len(parts) > 1:
                    text_part = parts[1]
                else:
                    text_part = line
                chunk_words = set(re.findall(r'\w+', text_part))
                overlap = len(quote_words & chunk_words)
                if overlap > best_score:
                    best_score = overlap
                    best_match = line
            # If good overlap (e.g., >50% of quote words), use it
            if best_match and best_score > len(quote_words) * 0.5:
                page_match = re.search(r'\[Page (\d+)', best_match)
                page = page_match.group(1) if page_match else None
                section_match = re.search(r'— ([^\]]+)', best_match)
                section = section_match.group(1) if section_match else None
                citations.append({"text": quote, "page": page, "section": section})
                # Remove the quote from answer
                answer = answer.replace(f'"{quote}"', '').strip()

    return {"answer": answer, "citations": citations}


# History builder

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


# LLM factory

def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,           # deterministic — important for medical answers
        request_timeout=30,      # hard timeout per request
        max_retries=2,           # automatic retry on transient failures
        openai_api_key=os.getenv("OPENAI_API_KEY"),
    )


# OpenAI error mapper 

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


# Greeting handler

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


# Main entry point 

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

    # 1. Intent: greeting or real question? 
    if _GREETING_PATTERNS.match(question.strip()):
        log.info("Greeting detected, skipping RAG", extra=ctx)
        return await _handle_greeting(question)

    # 2. Verify leaflet is indexed
    if not leaflet_exists(leaflet_id):
        raise ChatbotError(ErrorCode.LEAFLET_NOT_INDEXED, detail=f"leaflet_id={leaflet_id}")

    # 3. Expand query using history for vague follow-up questions 
    # Short/vague follow-ups like "tell me more" or "תוכל להסביר?" have no
    # keywords to match the leaflet. Prepend the last assistant answer so the
    # embedding search gets meaningful medical terms.
    search_query = question

    # 4. Retrieve relevant chunks
    with track_latency(log, "vector_search", ctx):
        relevant = query_chunks(leaflet_id, search_query, n_results=20)

    if not relevant:
        log.info("No relevant chunks found", extra=ctx)
        return {
            "answer": "This information is not available in the provided leaflet.",
            "citations": [],
            "is_greeting": False,
        }

    # 4. Build context string with page + section labels
    context_parts = []
    for chunk in relevant[:10]:  # Limit to top 10 to avoid context overflow
        label = f"[Page {chunk['page']}"
        if chunk.get("section"):
            label += f" — {chunk['section']}"
        label += "]"
        context_parts.append(f"{label}\n{chunk['text']}")

    context = "\n\n---\n\n".join(context_parts)

    # 5. Build message list: system → history → current question
    messages = [SystemMessage(content=MEDICAL_SYSTEM_PROMPT.format(context=context))]
    messages.extend(_build_history(history))
    messages.append(HumanMessage(content=question))

    # 6. LLM call with error handling
    llm = _get_llm()
    try:
        with track_latency(log, "llm_call", ctx):
            response = await llm.ainvoke(messages)
        metrics.record_llm_call(success=True)
    except Exception as exc:
        metrics.record_llm_call(success=False)
        raise _map_openai_error(exc) from exc

    # 7. Parse and return
    result = _parse_response(response.content, context)
    result["is_greeting"] = False

    # Log raw response for debugging citations
    log.info("LLM raw response", extra={"raw_response": response.content[:500]})  # Truncate for log

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