# MedAI — Medical Leaflet Assistant

> A RAG-powered chatbot that lets patients ask questions about their medication in **Hebrew or English**, with answers grounded solely in the uploaded leaflet — no hallucinations, every claim cited.

![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![React](https://img.shields.io/badge/React-18-61dafb)

---

## Demo

| Upload a Leaflet | Ask Questions | Cited Answers | Monitoring |
|---|---|---|---|
| Drag & drop PDF | Hebrew & English | Verbatim quotes with page numbers | Live metrics dashboard |

---

## Features

- **RAG pipeline** — answers come only from the uploaded document, never from the model's training data
- **Hebrew & English** — full RTL support, multi-query retrieval optimized for Hebrew morphology
- **Citations** — every answer includes verbatim quotes with page numbers, collapsible in the UI
- **Conversation history** — multi-turn chat with context across follow-up questions
- **Multiple sessions** — sidebar with rename, delete, and switch between past conversations
- **Monitoring dashboard** — live latency, LLM usage, error tracking
- **Privacy-first** — all data stays local; no PDF content sent to third-party storage
- **Mobile responsive** — slide-in sidebar drawer on small screens

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Browser (React)                       │
│  Sidebar │ Chat │ Home │ Monitoring                         │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP / REST
┌──────────────────────▼──────────────────────────────────────┐
│                   FastAPI  (main.py)                         │
│  Middleware: request_id · latency · structured JSON logs     │
│  Error handlers: ChatbotError → structured JSON response     │
└──────┬───────────────┬───────────────────┬──────────────────┘
       │               │                   │
┌──────▼──────┐ ┌──────▼──────┐  ┌────────▼────────┐
│ pdf_service │ │chat_service │  │   db_service    │
│             │ │             │  │                 │
│ extract text│ │ RAG pipeline│  │ SQLite          │
│ chunk text  │ │ intent detect│  │ chats + messages│
│ embed store │ │ history mgmt│  │ citations JSON  │
└──────┬──────┘ └──────┬──────┘  └─────────────────┘
       │               │
┌──────▼───────────────▼──────────────────────────────────────┐
│                   chroma_service                             │
│   ChromaDB (local)  ·  OpenAI text-embedding-3-small         │
│   Multi-query retrieval  ·  Keyword fallback                 │
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
| Observability | Custom + optional Sentry | JSON logs, in-memory metrics, request tracing |

### Frontend
| Component | Technology |
|---|---|
| Framework | React 18 |
| Styling | Tailwind CSS v4 |
| Charts | Recharts |
| Icons | Lucide React |
| Routing | React Router v6 |
| Build | Vite |

---

## Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+
- OpenAI API key

### Local Development

**1. Clone the repository**
```bash
git clone https://github.com/your-username/medai.git
cd medai
```

**2. Backend setup**
```bash
cd backend
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

**3. Start the backend**
```bash
uvicorn main:app --reload --port 8001
```

**4. Frontend setup**
```bash
cd frontend
npm install
npm run dev
```

**5. Open the app**
```
http://localhost:3000
```

### Docker (Production)

```bash
cp backend/.env.example backend/.env
# Add your OPENAI_API_KEY to backend/.env

docker compose up --build
```

The app will be available at `http://localhost`.

---

## Project Structure

```
medai/
├── backend/
│   ├── main.py                  # FastAPI app, routes, middleware
│   ├── errors.py                # Error catalog (ErrorCode enum + ChatbotError)
│   ├── observability.py         # Logging, metrics, Sentry integration
│   ├── requirements.txt
│   ├── .env.example
│   └── services/
│       ├── pdf_service.py       # PDF ingestion pipeline
│       ├── chroma_service.py    # Vector store operations
│       ├── chat_service.py      # RAG pipeline + LLM
│       └── db_service.py        # SQLite CRUD
│
└── frontend/
    └── src/
        ├── App.jsx              # Root — shared activeChat state
        ├── pages/
        │   ├── Home.jsx
        │   ├── Chat.jsx         # Chat page entry point
        │   └── Monitoring.jsx   # Metrics dashboard
        └── components/
            ├── layout/
            │   └── Layout.jsx   # Sidebar + main area, mobile drawer
            ├── sidebar/
            │   ├── Sidebar.jsx        # State + API calls
            │   ├── SidebarLogo.jsx
            │   ├── SidebarNav.jsx
            │   ├── RecentChats.jsx
            │   ├── ChatRow.jsx        # Rename + delete per chat
            │   └── SidebarDisclaimer.jsx
            └── chat/
                ├── Chat.jsx           # Orchestration + state
                ├── UploadScreen.jsx   # PDF drop zone
                ├── ChatHeader.jsx
                ├── ChatInput.jsx
                ├── Message.jsx        # Bubble + citations + copy
                ├── Citation.jsx       # Collapsible citation block
                └── CopyButton.jsx
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

### Metrics snapshot

```bash
curl http://localhost:8001/metrics
```

```json
{
  "uptime_seconds": 3600,
  "total_requests": 142,
  "llm_calls": 38,
  "llm_errors": 0,
  "pdf_uploads": 3,
  "errors_by_type": {},
  "latency_ms": {
    "avg": 1243.5,
    "min": 12.1,
    "max": 9800.0,
    "p95": 3200.0
  }
}
```

---

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | ✅ | — | OpenAI API key |
| `SENTRY_DSN` | ❌ | — | Sentry DSN for error tracking |
| `LOG_LEVEL` | ❌ | `INFO` | Logging level |
| `ENVIRONMENT` | ❌ | `development` | Used by Sentry |

---

## Observability

All logs are structured JSON, compatible with any log aggregator:

```json
{
  "timestamp": "2026-02-20T14:32:11+00:00",
  "level": "INFO",
  "logger": "main",
  "message": "Request completed",
  "request_id": "a3f2c891",
  "path": "/chats/abc/ask",
  "status": 200,
  "latency_ms": 1843.2
}
```

**Per-operation latency** is tracked for:
- `pdf_extract`, `pdf_chunk`, `pdf_embed_store`
- `vector_search`, `llm_call`, `openai_embed_batch`

**Optional integrations:**
- **Sentry** — set `SENTRY_DSN` in `.env`
- **Datadog / Loki / CloudWatch** — point at stdout, JSON is natively ingested
- **OpenTelemetry** — architecture is trace-ready (`request_id` propagated through all layers)

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