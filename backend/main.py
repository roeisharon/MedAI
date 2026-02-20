"""
main.py
─────────────────────────────────────────────────────────────────────────────
Medical Leaflet Chatbot — FastAPI application entrypoint.

Architecture overview:
  ┌─────────────┐    ┌──────────────┐    ┌───────────────┐
  │   FastAPI   │───▶│  pdf_service │───▶│ chroma_service│
  │  (this file)│    │  (ingestion) │    │ (vector store)│
  │             │    └──────────────┘    └───────────────┘
  │             │    ┌──────────────┐    ┌───────────────┐
  │             │───▶│ chat_service │───▶│  OpenAI API   │
  │             │    │  (RAG + LLM) │    └───────────────┘
  │             │    └──────────────┘
  │             │    ┌──────────────┐
  │             │───▶│  db_service  │───▶ SQLite (local)
  └─────────────┘    └──────────────┘

Request lifecycle:
  1. RequestLoggingMiddleware assigns a unique request_id and logs start/end
  2. Route handler runs business logic (pdf_service / chat_service / db_service)
  3. ChatbotError is caught by global handler → structured JSON error response
  4. Unhandled exceptions are caught, reported via observability.report_exception,
     and returned as a safe 500 with no internal details exposed
  5. Metrics updated throughout (requests, sessions, LLM calls, latency)

Storage:
  ./data/chatbot.db   — SQLite (chats + message history)
  ./chroma_db/        — ChromaDB (PDF vector embeddings)
  Both are git-ignored and never leave the user's machine.
"""

import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import uvicorn

load_dotenv()  # Load OPENAI_API_KEY and optional SENTRY_DSN from .env

from services.db_service import (
    init_db,
    create_chat, get_chat, list_chats, delete_chat, update_chat_title,
    add_message, get_messages, get_messages_for_llm,
)
from services.pdf_service import process_pdf
from services.chat_service import answer_question
from services.chroma_service import delete_leaflet
from errors import ChatbotError, ErrorCode
from observability import setup_logging, get_logger, metrics, report_exception, new_request_id

log = get_logger("main")


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs setup before the server accepts traffic, and cleanup on shutdown.
    - Configures structured JSON logging
    - Initialises SQLite schema
    """
    setup_logging()
    log.info("Medical Leaflet Chatbot starting up")
    init_db()
    yield
    log.info("Medical Leaflet Chatbot shutting down")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Medical Leaflet Chatbot API",
    description=(
        "Multi-session medical leaflet Q&A. "
        "All data is stored locally — no external databases, no user registration."
    ),
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request logging middleware ─────────────────────────────────────────────────

@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """
    Wraps every HTTP request with:
      • A unique request_id (injected into request.state and response header)
      • Structured log at request start and end
      • Latency measurement
      • Global request counter update
    """
    request_id = new_request_id()
    request.state.request_id = request_id
    start = time.perf_counter()

    log.info(
        "Request started",
        extra={
            "request_id": request_id,
            "method":     request.method,
            "path":       request.url.path,
            "client_ip":  request.client.host if request.client else "unknown",
        },
    )
    metrics.record_request()

    response = await call_next(request)

    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    metrics.record_latency(latency_ms)

    log.info(
        "Request completed",
        extra={
            "request_id": request_id,
            "method":     request.method,
            "path":       request.url.path,
            "status":     response.status_code,
            "latency_ms": latency_ms,
        },
    )

    response.headers["X-Request-ID"] = request_id
    return response


# ── Global error handlers ─────────────────────────────────────────────────────

@app.exception_handler(ChatbotError)
async def chatbot_error_handler(request: Request, exc: ChatbotError):
    """
    Handles all application-level errors (ChatbotError).
    Returns a structured JSON body safe to display in the frontend.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    log.warning(
        f"ChatbotError: {exc.error_code}",
        extra={
            "request_id":  request_id,
            "error_code":  exc.error_code,
            "status_code": exc.status_code,
            "detail":      str(exc.detail),
        },
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail,
        headers={"X-Request-ID": request_id},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Safety net for any unhandled exception.
    Logs full traceback + reports to Sentry if configured.
    Returns a safe 500 with no internal details exposed to the client.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    report_exception(exc, context={"request_id": request_id, "path": request.url.path})
    return JSONResponse(
        status_code=500,
        content={
            "error_code":    ErrorCode.INTERNAL_ERROR,
            "user_message":  "An unexpected error occurred. Please try again or restart the application.",
            "detail":        None,
        },
        headers={"X-Request-ID": request_id},
    )


# ── Schemas ───────────────────────────────────────────────────────────────────

class RenameChatRequest(BaseModel):
    title: str

class AskRequest(BaseModel):
    question: str


# ── Greeting factory ──────────────────────────────────────────────────────────

_GREETING_MESSAGE = (
    "Hello! I'm your medical leaflet assistant. I've loaded your leaflet and I'm ready to help. "
    "You can ask me anything about this medication — dosage, side effects, warnings, interactions, "
    "and more. What would you like to know?"
)


# ── Chat management endpoints ─────────────────────────────────────────────────

@app.post("/chats", summary="Create a new chat by uploading a PDF leaflet")
async def create_new_chat(
    request: Request,
    file: UploadFile = File(...),
    title: Optional[str] = None,
):
    """
    Upload a PDF medical leaflet and start a new independent chat session.
    An initial greeting from the assistant is automatically added to the history.

    Returns the chat object (including `id`) for use in subsequent requests.
    """
    request_id = request.state.request_id

    if not file.filename.lower().endswith(".pdf"):
        raise ChatbotError(ErrorCode.PDF_INVALID_FORMAT, detail=f"filename={file.filename}")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise ChatbotError(ErrorCode.PDF_EMPTY)

    log.info("PDF upload received", extra={"request_id": request_id, "pdf_filename": file.filename, "size_bytes": len(pdf_bytes)})

    pdf_info  = await process_pdf(pdf_bytes, file.filename)
    leaflet_id = pdf_info["leaflet_id"]
    page_count = pdf_info["page_count"]
    chat = create_chat(leaflet_id=leaflet_id, filename=file.filename, title=title)

    # ── Auto-insert greeting as first assistant message ───────────────────────
    # This gives the frontend a message to display immediately after upload,
    # and sets a friendly tone before the user asks any questions.
    add_message(chat["id"], role="assistant", content=_GREETING_MESSAGE, citations=[])

    metrics.record_session()
    log.info("Chat session created", extra={"request_id": request_id, "chat_id": chat["id"], "leaflet_id": leaflet_id})

    return {**chat, "greeting": _GREETING_MESSAGE, "page_count": page_count}


@app.get("/chats", summary="List all chats (newest first)")
async def list_all_chats():
    return list_chats()


@app.get("/chats/{chat_id}", summary="Get chat details")
async def get_chat_detail(chat_id: str):
    chat = get_chat(chat_id)
    if not chat:
        raise ChatbotError(ErrorCode.CHAT_NOT_FOUND, detail=f"chat_id={chat_id}")
    return chat


@app.patch("/chats/{chat_id}", summary="Rename a chat")
async def rename_chat(chat_id: str, body: RenameChatRequest):
    chat = update_chat_title(chat_id, body.title)
    if not chat:
        raise ChatbotError(ErrorCode.CHAT_NOT_FOUND, detail=f"chat_id={chat_id}")
    return chat


@app.delete("/chats/{chat_id}", summary="Delete a chat and all its messages")
async def remove_chat(chat_id: str):
    """
    Deletes the chat and its full message history from SQLite.
    Also removes the PDF vectors from ChromaDB — but only if no other
    chat references the same leaflet (same PDF content hash).
    """
    chat = get_chat(chat_id)
    if not chat:
        raise ChatbotError(ErrorCode.CHAT_NOT_FOUND, detail=f"chat_id={chat_id}")

    leaflet_id = chat["leaflet_id"]
    other_chats = [c for c in list_chats() if c["leaflet_id"] == leaflet_id and c["id"] != chat_id]
    if not other_chats:
        delete_leaflet(leaflet_id)  # Safe to remove vectors — no other chat uses this PDF

    delete_chat(chat_id)
    log.info("Chat removed", extra={"chat_id": chat_id, "leaflet_id": leaflet_id})
    return {"message": f"Chat '{chat_id}' and all its messages have been deleted."}


# ── Message endpoints ─────────────────────────────────────────────────────────

@app.get("/chats/{chat_id}/messages", summary="Get full message history for a chat")
async def get_chat_messages(chat_id: str):
    if not get_chat(chat_id):
        raise ChatbotError(ErrorCode.CHAT_NOT_FOUND, detail=f"chat_id={chat_id}")
    return get_messages(chat_id)


@app.post("/chats/{chat_id}/ask", summary="Ask a question in a chat")
async def ask_in_chat(request: Request, chat_id: str, body: AskRequest):
    """
    Ask a question grounded strictly in the chat's uploaded leaflet.

    Pipeline:
      1. Validate chat exists
      2. Persist user message to SQLite
      3. Retrieve conversation history (for follow-up awareness)
      4. Run RAG pipeline (or greeting handler if social message)
      5. Persist assistant response with citations (including page + section)
      6. Return answer + citations to caller

    Citations include page number and section heading where available.
    """
    request_id = request.state.request_id

    chat = get_chat(chat_id)
    if not chat:
        raise ChatbotError(ErrorCode.CHAT_NOT_FOUND, detail=f"chat_id={chat_id}")

    if not body.question.strip():
        raise ChatbotError(ErrorCode.CHAT_EMPTY_QUESTION)

    # Persist user message first (so it's in history for future turns)
    add_message(chat_id, role="user", content=body.question)

    # Get history excluding the message we just inserted (chat_service appends it)
    history = get_messages_for_llm(chat_id)[:-1]

    log.info(
        "Processing question",
        extra={
            "request_id":   request_id,
            "chat_id":      chat_id,
            "leaflet_id":   chat["leaflet_id"],
            "question_len": len(body.question),
            "history_turns": len(history),
        },
    )

    result = await answer_question(
        leaflet_id=chat["leaflet_id"],
        question=body.question,
        history=history,
        request_id=request_id,
    )

    # Persist assistant response
    assistant_msg = add_message(
        chat_id,
        role="assistant",
        content=result["answer"],
        citations=result["citations"],
    )

    return {
        "message_id":  assistant_msg["id"],
        "answer":      result["answer"],
        "citations":   result["citations"],   # [{text, page, section}]
        "is_greeting": result.get("is_greeting", False),
        "chat_id":     chat_id,
        "request_id":  request_id,
    }


# ── Observability endpoints ───────────────────────────────────────────────────

@app.get("/metrics", summary="Usage metrics and latency statistics")
async def get_metrics():
    """
    Returns in-memory usage counters and latency percentiles.
    Resets on server restart. For persistent metrics, configure an
    external aggregator to scrape this endpoint.
    """
    return metrics.summary()


@app.get("/health", summary="Health check")
async def health():
    return {"status": "ok", "version": "3.0.0"}


# ── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)