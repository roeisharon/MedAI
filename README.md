# MedAI — Medical Leaflet Assistant

> A RAG-powered chatbot that lets patients ask questions about their medication in **Hebrew or English**, with answers grounded solely in the uploaded leaflet — no hallucinations, every claim cited.

![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![React](https://img.shields.io/badge/React-18-61dafb)

---

## Demo

| Upload a Leaflet | Ask Questions | Cited Answers |
|---|---|---|
| Drag & drop PDF | Hebrew & English | Verbatim quotes with page numbers |

---

## Features

- **RAG pipeline** — answers come only from the uploaded document, never from the model's training data
- **Hebrew & English** — full RTL support, multi-query retrieval optimized for Hebrew morphology
- **Citations** — every answer includes verbatim quotes with page numbers, collapsible in the UI
- **Conversation history** — multi-turn chat with context across follow-up questions
- **Multiple sessions** — sidebar with rename, delete, and switch between past conversations
- **Privacy-first** — all data stays local; no PDF content sent to third-party storage
- **Mobile responsive** — slide-in sidebar drawer on small screens

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Browser (React)                      │
│  Sidebar │ Chat │ Home                                      │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP / REST
┌──────────────────────▼──────────────────────────────────────┐
│                   FastAPI  (main.py)                        │
│  Middleware: request_id · latency · structured JSON logs    │
│  Error handlers: ChatbotError → structured JSON response    │
└──────┬───────────────┬──────────────────┬───────────────────┘
       │               │                  │
┌──────▼──────┐ ┌──────▼──────┐  ┌────────▼────────┐
│ pdf_service │ │chat_service │  │   db_service    │
│             │ │             │  │                 │
│ extract text│ │ RAG pipeline│  │ SQLite          │
│ chunk text  │ │intent detect│  │ chats + messages│
│ embed store │ │ history mgmt│  │ citations JSON  │
└──────┬──────┘ └──────┬──────┘  └─────────────────┘
       │               │
┌──────▼───────────────▼──────────────────────────────────────┐
│                   chroma_service                            │
│   ChromaDB (local)  ·  OpenAI text-embedding-3-small        │
│   Multi-query retrieval  ·  Keyword fallback                │
└─────────────────────────────────────────────────────────────┘
```

### RAG Flow

```
User question
    │
    ├─ Greeting? → warm response, skip RAG
    │
    ▼
Embed question  →  ChromaDB cosine search (scoped to leaflet)
    │
    ▼
Top-8 chunks + keyword fallback
    │
    ▼
Build prompt: system(grounding rules + chunks) + history + question
    │
    ▼
GPT-4o-mini (temperature=0)
    │
    ▼
Parse <answer> + <citations> XML
    │
    ▼
Persist to SQLite → return to frontend
```

---

## Tech Stack

### Backend
| Component | Technology | Why |
|---|---|---|
| Web framework | FastAPI | Async, auto-docs, Pydantic validation |
| LLM | GPT-4o-mini via LangChain | Cost-efficient, sufficient for extraction |
| Embeddings | text-embedding-3-small | 1536-dim, strong multilingual |
| Vector store | ChromaDB (local) | No cloud, privacy-first, cosine similarity |
| PDF parsing | pypdf | Lightweight, per-page text extraction |
| Database | SQLite (WAL mode) | Zero-config, local-first, persistent |
| Observability | Custom (JSON logs + /metrics) | Structured logs, in-memory metrics, request tracing |

### Frontend
| Component | Technology |
|---|---|
| Framework | React 18 |
| Styling | Tailwind CSS v4 |
| Icons | Lucide React |
| Routing | React Router v6 |
| Build | Vite |

---

## Getting Started

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- An [OpenAI API key](https://platform.openai.com/api-keys)

> No Python or Node.js installation required — Docker handles everything.

---

### 🚀 First-Time Setup

**1. Clone the repository**
```bash
git clone https://github.com/roeisharon/medai.git
cd medai
```

**2. Create your environment file**
```bash
touch .env
```

Open `.env` and add your OpenAI API key:
```env
OPENAI_API_KEY=sk-...your-key-here...
```

**3. Build and start everything**
```bash
docker compose up --build
```

This single command will:
- Build the Python backend image and install all dependencies
- Build the React frontend and compile it with nginx
- Start both containers and wire them together
- Wait for the backend to pass its health check before serving the frontend

> ⏱ First build takes ~2–3 minutes (downloading base images + installing packages). Subsequent builds are much faster thanks to Docker layer caching.

**4. Open the app**
```
http://localhost
```

The backend API is also directly accessible at `http://localhost:8000` (useful for Swagger docs at `http://localhost:8000/docs`).

---

### 🔄 Day-to-Day Usage (After First Build)

**Start the system:**
```bash
docker compose up
```

**Stop the system:**
```bash
docker compose down
```

Your data (uploaded PDFs, chat history, vectors) is stored in Docker named volumes and **persists across restarts**. Starting and stopping does not lose any data.

---

### 🔧 Useful Commands

**View live logs:**
```bash
# All containers
docker compose logs -f

# Backend only
docker compose logs -f backend

# Frontend only
docker compose logs -f frontend
```

**Check container status:**
```bash
docker compose ps
# Both containers should show "running" and backend should show "(healthy)"
```

**Verify the backend is healthy:**
```bash
curl http://localhost:8000/health
# Expected: {"status": "ok"}
```

**View live metrics:**
```bash
curl http://localhost:8000/metrics
```

**Rebuild after code changes:**
```bash
docker compose up --build
```

---

### 🗑 Data Management

**Reset all data** (wipes all chats, messages, and uploaded PDFs):
```bash
docker compose down -v
```
> The `-v` flag removes the named volumes. Next `docker compose up` starts fresh.

**Reset only and restart immediately:**
```bash
docker compose down -v && docker compose up
```

---

### 🩺 Troubleshooting

**Backend container exits immediately:**
```bash
docker compose logs backend
# Usually means OPENAI_API_KEY is missing or invalid in .env
```

**Frontend shows "Could not reach the backend":**
```bash
docker compose ps
# Check backend is healthy. If not: docker compose restart backend
```

**Port 80 already in use:**
```bash
# Edit docker-compose.yml and change "80:80" to e.g. "8080:80"
# Then visit http://localhost:8080
```

**Full clean rebuild** (if something is broken and you want to start fresh):
```bash
docker compose down -v
docker system prune -f
docker compose up --build
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/chats` | Upload PDF, create chat session |
| `GET` | `/chats` | List all chats |
| `GET` | `/chats/{id}` | Get chat details |
| `PATCH` | `/chats/{id}` | Rename chat |
| `DELETE` | `/chats/{id}` | Delete chat + vectors |
| `POST` | `/chats/{id}/ask` | Ask a question |
| `GET` | `/chats/{id}/messages` | Get message history |
| `GET` | `/metrics` | Observability snapshot |
| `GET` | `/health` | Health check |

### Example: Ask a question

```bash
curl -X POST http://localhost:8001/chats/{chat_id}/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "מה הם תופעות הלוואי של הטיפול?"}'
```

```json
{
  "answer": "הטיפול עלול לגרום למספר תופעות לוואי...",
  "citations": [
    {
      "text": "כל התרופות עלולות לגרום לתופעות לוואי",
      "page": 9,
      "section": "תופעות לוואי"
    }
  ],
  "is_greeting": false
}
```

---

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | ✅ | — | OpenAI API key |
| `LOG_LEVEL` | ❌ | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`) |

---

## Observability

### Metrics Endpoint

The system exposes a live metrics snapshot at:

```
GET http://localhost:8000/metrics
```

```bash
curl http://localhost:8000/metrics
```

```json
{
  "uptime_seconds": 3600,
  "total_requests": 142,
  "total_sessions": 4,
  "questions_asked": 38,
  "llm_calls": 38,
  "llm_errors": 0,
  "pdf_uploads": 3,
  "errors_by_type": {},
  "latency_ms": {
    "count": 142,
    "avg": 1243.5,
    "min": 12.1,
    "max": 9800.0,
    "p95": 3200.0
  }
}
```

| Field | Description |
|---|---|
| `uptime_seconds` | Time since last server restart |
| `total_sessions` | PDF uploads that created a new chat |
| `questions_asked` | User questions submitted (key event) |
| `llm_calls` | Total OpenAI API calls made |
| `llm_errors` | Failed LLM calls |
| `pdf_uploads` | Successfully processed PDFs |
| `errors_by_type` | Count per error code (e.g. `llm_timeout`, `pdf_no_text`) |
| `latency_ms.p95` | 95th percentile response time (available after 20+ requests) |

> Metrics are in-memory and reset on server restart. For persistence, point a scraper at this endpoint.

### Structured Logs

Every request emits structured JSON to stdout — readable in the terminal and compatible with any log aggregator:

```json
{"timestamp": "2026-02-20T14:32:11+00:00", "level": "INFO", "logger": "main", "message": "user_question", "event": "user_question", "request_id": "a3f2c891", "chat_id": "abc-123", "question": "מה תופעות הלוואי?", "question_len": 18, "history_turns": 2}
{"timestamp": "2026-02-20T14:32:13+00:00", "level": "INFO", "logger": "chat_service", "message": "llm_call completed", "operation": "llm_call", "latency_ms": 1843.2, "request_id": "a3f2c891"}
{"timestamp": "2026-02-20T14:32:13+00:00", "level": "INFO", "logger": "main", "message": "Request completed", "request_id": "a3f2c891", "status": 200, "latency_ms": 1901.5}
```

**Per-operation latency** is tracked for: `pdf_extract`, `pdf_chunk`, `pdf_embed_store`, `vector_search`, `llm_call`, `openai_embed_batch`

---

## Key Design Decisions

**Privacy-first storage** — ChromaDB runs locally. Medical PDF content never leaves the user's machine and is never sent to third-party vector storage.

**Idempotent ingestion** — PDFs are identified by SHA-256 content hash. Re-uploading the same file is a no-op; no duplicate indexing.

**Full-document chunking** — text is chunked across the whole document rather than per-page, avoiding artificial splits at page boundaries that break medical definitions and sentences.

**Multi-query Hebrew retrieval** — each question is searched twice: once as written, once with Hebrew question words stripped. A keyword fallback scans all chunks for exact term matches, catching cases where embedding similarity alone is insufficient.

**Strict grounding** — the system prompt prohibits the model from using any knowledge outside the provided excerpts. Output is forced into `<answer>/<citations>` XML, making it parseable and verifiable.

---

## License

MIT © 2026