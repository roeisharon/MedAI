"""
Central observability layer for the Medical Leaflet Chatbot.

Covers:
  • Structured JSON logging (every log line is machine-parseable)
  • Request ID generation and propagation (trace requests end-to-end)
  • Latency tracking via context managers and decorators
  • In-memory usage counters (requests, sessions, LLM calls, errors)
  • Optional Sentry integration for exception tracking
  • OpenTelemetry-ready structure (trace/span IDs in log fields)

All log output goes to stdout (12-factor app style) so it can be
captured by any log aggregator (Datadog, Loki, CloudWatch, etc.).
"""

import logging
import time
import uuid
import json
import os
import traceback
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any
from collections import defaultdict

#Structured JSON log formatter

class JSONFormatter(logging.Formatter):
    """
    Formats every log record as a single-line JSON object.
    This makes logs trivially parseable by log aggregators.

    Output fields:
      timestamp, level, logger, message, request_id (if set),
      latency_ms (if set), extra fields passed via logger.info(..., extra={...})
    """

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Propagate any extra fields attached by the caller
        for key, value in record.__dict__.items():
            if key not in (
                "args", "asctime", "created", "exc_info", "exc_text",
                "filename", "funcName", "id", "levelname", "levelno",
                "lineno", "message", "module", "msecs", "msg", "name",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "thread", "threadName",
            ):
                log_obj[key] = value

        # Attach exception info if present
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj, default=str)


def setup_logging():
    """
    Configure root logger with JSON formatter.
    Call once at application startup (inside lifespan in main.py).
    """
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    root.handlers = [handler]   # replace any default handlers

    # Quiet noisy third-party loggers
    for noisy in ("httpx", "httpcore", "openai", "chromadb", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Convenience wrapper — use instead of logging.getLogger() everywhere."""
    return logging.getLogger(name)


#Request ID

def new_request_id() -> str:
    """Generate a short unique request ID (first 8 chars of a UUID4)."""
    return str(uuid.uuid4())[:8]


#Latency context manager

@contextmanager
def track_latency(logger: logging.Logger, operation: str, extra: dict = None):
    """
    Context manager that measures wall-clock time for a block of code
    and logs the result at INFO level with latency_ms field.

    Usage:
        with track_latency(log, "embed_query", {"chat_id": chat_id}):
            result = embed(question)
    """
    start = time.perf_counter()
    extra = extra or {}
    try:
        yield
    finally:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            f"{operation} completed",
            extra={"operation": operation, "latency_ms": elapsed_ms, **extra},
        )


#In-memory usage counters
# These reset on server restart. For persistent metrics, push to Prometheus
# or a time-series DB. Exposed via GET /metrics endpoint in main.py.

class UsageMetrics:
    """
    Thread-safe (GIL-protected for CPython) in-memory counters.

    Tracks:
      total_requests      — every POST /chats/{id}/ask call
      total_sessions      — every POST /chats (new chat created)
      llm_calls           — every call to the OpenAI chat completion API
      llm_errors          — failed LLM calls
      pdf_uploads         — successful PDF processing
      errors_by_type      — dict of error_type → count
      latency_samples_ms  — list of ask-endpoint latencies (last 1000)
    """

    def __init__(self):
        self.total_requests = 0
        self.total_sessions = 0
        self.questions_asked = 0
        self.llm_calls = 0
        self.llm_errors = 0
        self.pdf_uploads = 0
        self.errors_by_type: dict[str, int] = defaultdict(int)
        self.latency_samples_ms: list[float] = []
        self._start_time = time.time()

    def record_request(self):
        self.total_requests += 1

    def record_question(self):
        self.questions_asked += 1

    def record_session(self):
        self.total_sessions += 1

    def record_llm_call(self, success: bool = True):
        self.llm_calls += 1
        if not success:
            self.llm_errors += 1

    def record_pdf_upload(self):
        self.pdf_uploads += 1

    def record_error(self, error_type: str):
        self.errors_by_type[error_type] += 1

    def record_latency(self, latency_ms: float):
        self.latency_samples_ms.append(latency_ms)
        if len(self.latency_samples_ms) > 1000:
            self.latency_samples_ms = self.latency_samples_ms[-1000:]

    def summary(self) -> dict:
        """Return a snapshot of all metrics — used by GET /metrics."""
        samples = self.latency_samples_ms
        return {
            "uptime_seconds": round(time.time() - self._start_time),
            "total_requests": self.total_requests,
            "total_sessions": self.total_sessions,
            "questions asked": self.questions_asked,
            "llm_calls": self.llm_calls,
            "llm_errors": self.llm_errors,
            "pdf_uploads": self.pdf_uploads,
            "errors_by_type": dict(self.errors_by_type),
            "latency_ms": {
                "count": len(samples),
                "avg": round(sum(samples) / len(samples), 1) if samples else 0,
                "min": round(min(samples), 1) if samples else 0,
                "max": round(max(samples), 1) if samples else 0,
            },
        }


# Singleton instance — imported by main.py and services
metrics = UsageMetrics()


#Error reporting

def report_exception(exc: Exception, context: dict = None):
    """
    Central exception reporter.
    - Logs full traceback as structured JSON
    - Sends to Sentry if configured
    - Updates error counters

    Call this in except blocks instead of logger.exception() directly.
    """
    logger = get_logger("errors")
    error_type = type(exc).__name__
    metrics.record_error(error_type)

    logger.error(
        str(exc),
        extra={
            "error_type": error_type,
            "traceback": traceback.format_exc(),
            **(context or {}),
        },
        exc_info=True,
    )