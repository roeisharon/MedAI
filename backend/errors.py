"""
errors.py
─────────────────────────────────────────────────────────────────────────────
Centralized error catalog for the Medical Leaflet Chatbot.

Design goals:
  • Every error the frontend might display has a stable machine-readable
    `error_code` (snake_case string) so the UI can localise or style it.
  • `user_message` is safe to show directly to the end user.
  • `detail` carries debug info (never shown to users, logged server-side).
  • HTTP status codes are consistent with REST conventions.

Usage:
    raise ChatbotError(ErrorCode.PDF_NO_TEXT)
    raise ChatbotError(ErrorCode.LLM_TIMEOUT, detail="Timed out after 30s")
"""

from enum import Enum
from fastapi import HTTPException


class ErrorCode(str, Enum):
    # ── PDF / Upload errors ──────────────────────────────────────────────────
    PDF_INVALID_FORMAT   = "pdf_invalid_format"
    PDF_NO_TEXT          = "pdf_no_text"
    PDF_EMPTY            = "pdf_empty"
    PDF_TOO_LARGE        = "pdf_too_large"

    # ── Chat errors ──────────────────────────────────────────────────────────
    CHAT_NOT_FOUND       = "chat_not_found"
    CHAT_EMPTY_QUESTION  = "chat_empty_question"

    # ── LLM / OpenAI errors ──────────────────────────────────────────────────
    LLM_TIMEOUT          = "llm_timeout"
    LLM_RATE_LIMIT       = "llm_rate_limit"
    LLM_API_ERROR        = "llm_api_error"
    LLM_CONTEXT_TOO_LONG = "llm_context_too_long"

    # ── Vector DB errors ─────────────────────────────────────────────────────
    VECTOR_DB_ERROR      = "vector_db_error"
    LEAFLET_NOT_INDEXED  = "leaflet_not_indexed"

    # ── Generic ──────────────────────────────────────────────────────────────
    INTERNAL_ERROR       = "internal_error"
    SERVICE_UNAVAILABLE  = "service_unavailable"


# Maps each error code → (http_status, user-facing message)
_ERROR_MAP: dict[ErrorCode, tuple[int, str]] = {
    ErrorCode.PDF_INVALID_FORMAT:   (400, "The uploaded file is not a valid PDF. Please upload a PDF document."),
    ErrorCode.PDF_NO_TEXT:          (422, "The PDF appears to be scanned or image-based and contains no readable text. Please use a PDF with selectable text."),
    ErrorCode.PDF_EMPTY:            (400, "The uploaded file is empty. Please upload a valid PDF."),
    ErrorCode.PDF_TOO_LARGE:        (413, "The PDF is too large. Please upload a file under 20MB."),

    ErrorCode.CHAT_NOT_FOUND:       (404, "Chat session not found. It may have been deleted."),
    ErrorCode.CHAT_EMPTY_QUESTION:  (400, "Please enter a question before sending."),

    ErrorCode.LLM_TIMEOUT:          (504, "The AI service took too long to respond. Please try again in a moment."),
    ErrorCode.LLM_RATE_LIMIT:       (429, "Too many requests to the AI service. Please wait a moment and try again."),
    ErrorCode.LLM_API_ERROR:        (502, "The AI service returned an error. Please try again shortly."),
    ErrorCode.LLM_CONTEXT_TOO_LONG: (422, "The question or conversation is too long to process. Please start a new chat."),

    ErrorCode.VECTOR_DB_ERROR:      (500, "An error occurred while searching the leaflet. Please try again."),
    ErrorCode.LEAFLET_NOT_INDEXED:  (404, "The leaflet for this chat could not be found. The PDF may need to be re-uploaded."),

    ErrorCode.INTERNAL_ERROR:       (500, "An unexpected error occurred. Please try again or restart the application."),
    ErrorCode.SERVICE_UNAVAILABLE:  (503, "The service is temporarily unavailable. Please try again shortly."),
}


class ChatbotError(HTTPException):
    """
    Application-level exception that carries a structured error payload.
    Caught by the global exception handler in main.py and serialised to JSON.

    Response body shape:
    {
        "error_code": "llm_rate_limit",
        "user_message": "Too many requests...",
        "detail": "optional debug info (server-side only)"
    }
    """

    def __init__(self, code: ErrorCode, detail: str = None):
        status_code, user_message = _ERROR_MAP.get(code, (500, "An unexpected error occurred."))
        super().__init__(
            status_code=status_code,
            detail={
                "error_code": code.value,
                "user_message": user_message,
                "detail": detail,          # None in production-safe responses
            },
        )
        self.error_code = code
        self.user_message = user_message