"""
db_service.py
─────────────────────────────────────────────────────────────────────────────
SQLite persistence layer for chats and messages.

Schema:
  chats    — one row per chat session (linked to a leaflet PDF)
  messages — one row per user/assistant turn, with citations stored as JSON

Design decisions:
  • SQLite is used because the app is local-first (one user per install).
    No network calls, no credentials, zero-config.
  • WAL (Write-Ahead Logging) mode is enabled for safe concurrent reads
    (e.g., frontend polling while a response streams).
  • Foreign key cascade deletes messages automatically when a chat is deleted.
  • Citations are stored as a JSON array inside a TEXT column — simple and
    sufficient for this scale; no need for a separate citations table.
  • DB path defaults to ./data/chatbot.db, git-ignored.
"""

import sqlite3
import uuid
import json
from datetime import datetime, timezone
from pathlib import Path
from contextlib import contextmanager
from typing import Optional

from observability import get_logger

log = get_logger("db_service")

DB_PATH = Path("./data/chatbot.db")


def init_db():
    """
    Create the database file and tables if they don't exist.
    Safe to call multiple times (uses CREATE IF NOT EXISTS).
    Called once at application startup via FastAPI lifespan.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS chats (
                id          TEXT PRIMARY KEY,
                title       TEXT NOT NULL,
                leaflet_id  TEXT NOT NULL,
                filename    TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id          TEXT PRIMARY KEY,
                chat_id     TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
                role        TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content     TEXT NOT NULL,
                citations   TEXT NOT NULL DEFAULT '[]',
                created_at  TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id);
            CREATE INDEX IF NOT EXISTS idx_chats_updated    ON chats(updated_at DESC);
        """)
    log.info("Database initialised", extra={"db_path": str(DB_PATH)})


@contextmanager
def get_conn():
    """
    Context manager that opens a connection, commits on success,
    rolls back on any exception, and always closes.
    Thread-safe for CPython (GIL) in a single-user local app.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _now() -> str:
    """UTC ISO-8601 timestamp string."""
    return datetime.now(timezone.utc).isoformat()


# ── Chats ─────────────────────────────────────────────────────────────────────

def create_chat(leaflet_id: str, filename: str, title: Optional[str] = None) -> dict:
    """Insert a new chat row. Title defaults to the filename."""
    chat_id = str(uuid.uuid4())
    now = _now()
    title = title or f"Leaflet: {filename}"
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO chats (id, title, leaflet_id, filename, created_at, updated_at) VALUES (?,?,?,?,?,?)",
            (chat_id, title, leaflet_id, filename, now, now),
        )
    log.info("Chat created", extra={"chat_id": chat_id, "leaflet_id": leaflet_id})
    return get_chat(chat_id)


def get_chat(chat_id: str) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM chats WHERE id = ?", (chat_id,)).fetchone()
    return dict(row) if row else None


def list_chats() -> list[dict]:
    """Return all chats sorted by most recently active."""
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM chats ORDER BY updated_at DESC").fetchall()
    return [dict(r) for r in rows]


def delete_chat(chat_id: str) -> bool:
    """Delete chat + all its messages (cascade). Returns False if not found."""
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
    deleted = cur.rowcount > 0
    if deleted:
        log.info("Chat deleted", extra={"chat_id": chat_id})
    return deleted


def update_chat_title(chat_id: str, title: str) -> Optional[dict]:
    with get_conn() as conn:
        conn.execute(
            "UPDATE chats SET title = ?, updated_at = ? WHERE id = ?",
            (title, _now(), chat_id),
        )
    return get_chat(chat_id)


def _touch_chat(chat_id: str, conn):
    """Bump updated_at so chats sort correctly after new messages."""
    conn.execute("UPDATE chats SET updated_at = ? WHERE id = ?", (_now(), chat_id))


# ── Messages ──────────────────────────────────────────────────────────────────

def add_message(
    chat_id: str,
    role: str,
    content: str,
    citations: list[dict] = None,   # [{"text", "page", "section"}]
) -> dict:
    """Persist a single message turn and bump the parent chat's updated_at."""
    msg_id = str(uuid.uuid4())
    now = _now()
    citations_json = json.dumps(citations or [])
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (id, chat_id, role, content, citations, created_at) VALUES (?,?,?,?,?,?)",
            (msg_id, chat_id, role, content, citations_json, now),
        )
        _touch_chat(chat_id, conn)
    return {
        "id":         msg_id,
        "chat_id":    chat_id,
        "role":       role,
        "content":    content,
        "citations":  citations or [],
        "created_at": now,
    }


def get_messages(chat_id: str) -> list[dict]:
    """Full message history for a chat, oldest first."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE chat_id = ? ORDER BY created_at ASC",
            (chat_id,),
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["citations"] = json.loads(d["citations"])
        result.append(d)
    return result


def get_messages_for_llm(chat_id: str) -> list[dict]:
    """
    Slim version for LLM context: only role + content, oldest first.
    Citations are omitted since they're for the UI, not the model.
    """
    messages = get_messages(chat_id)
    return [{"role": m["role"], "content": m["content"]} for m in messages]