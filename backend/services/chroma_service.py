"""
Vector storage layer built on ChromaDB (local persistent store).
"""

import os
import re
import chromadb
from chromadb.config import Settings
from langchain_openai import OpenAIEmbeddings
from errors import ChatbotError, ErrorCode
from observability import get_logger, track_latency

log = get_logger("chroma_service")

COLLECTION_NAME = "medical_leaflets"

_client = chromadb.PersistentClient(
    path="./chroma_db",
    settings=Settings(anonymized_telemetry=False),
)


def _get_collection():
    return _client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def _get_embedder():
    return OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=os.getenv("OPENAI_API_KEY"),
    )


# Hebrew question/filler words to strip before keyword embedding search
_HEBREW_STOPWORDS = re.compile(
    r'\b(מה|מהם|מהן|איך|כיצד|מתי|היכן|למה|מדוע|האם|זה|זו|הם|הן|של|עם|על|את|לי|לנו|לך|הוא|היא|כמה|איזה|איזו|אילו|תסביר|תגיד|ספר|פרט|הסבר|לי|על)\b',
    re.UNICODE
)

def _strip_stopwords(question: str) -> str:
    clean = re.sub(r'[?!.,;:״\'"()]', ' ', question)
    return _HEBREW_STOPWORDS.sub('', clean).strip()


# Write

async def store_chunks(leaflet_id: str, chunks: list[dict]):
    try:
        collection = _get_collection()
        embedder   = _get_embedder()
        texts      = [c["text"] for c in chunks]

        with track_latency(log, "openai_embed_batch", {"leaflet_id": leaflet_id, "n_chunks": len(chunks)}):
            embeddings = embedder.embed_documents(texts)

        ids = [f"{leaflet_id}__chunk_{c['chunk_index']}" for c in chunks]
        metadatas = [
            {
                "leaflet_id":  leaflet_id,
                "chunk_index": c["chunk_index"],
                "page":        c["page"],
                "section":     c.get("section") or "",
            }
            for c in chunks
        ]

        collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)

    except ChatbotError:
        raise
    except Exception as exc:
        raise ChatbotError(ErrorCode.VECTOR_DB_ERROR, detail=str(exc)) from exc


# Read 

def _query_single(collection, embedder, query: str, leaflet_id: str, n_results: int) -> list[dict]:
    emb = embedder.embed_query(query)
    results = collection.query(
        query_embeddings=[emb],
        n_results=n_results,
        where={"leaflet_id": leaflet_id},
        include=["documents", "metadatas", "distances"],
    )
    if not results["documents"] or not results["documents"][0]:
        return []
    return [
        {
            "text":    doc,
            "page":    meta.get("page", "?"),
            "section": meta.get("section") or None,
            "score":   round(1 - dist, 4),
        }
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        )
    ]


def query_chunks(leaflet_id: str, question: str, n_results: int = 20) -> list[dict]:
    try:
        collection = _get_collection()
        embedder   = _get_embedder()

        seen: dict[str, dict] = {}

        # Query 1: original question as-is
        for r in _query_single(collection, embedder, question, leaflet_id, n_results):
            if r["text"] not in seen or r["score"] > seen[r["text"]]["score"]:
                seen[r["text"]] = r

        # Query 2: keywords only (strip stopwords + punctuation)
        keywords = _strip_stopwords(question)
        if keywords and keywords != question:
            for r in _query_single(collection, embedder, keywords, leaflet_id, n_results):
                if r["text"] not in seen or r["score"] > seen[r["text"]]["score"]:
                    seen[r["text"]] = r

        ranked = sorted(seen.values(), key=lambda x: x["score"], reverse=True)

        # Keyword fallback (exact + morphological variants)
        # Handles cases where embedding similarity misses due to Hebrew prefixes

        clean_q = re.sub(r'[?!.,;:״\'"()]', ' ', question)
        question_words = [w for w in re.findall(r'[א-ת\w]{3,}', clean_q) if len(w) >= 3]

        hebrew_prefixes = ['ה', 'ו', 'ב', 'ל', 'מ', 'כ', 'ש', 'מה', 'של', 'על']
        expanded_words = set(question_words)
        for word in question_words:
            # strip prefix → root
            for prefix in hebrew_prefixes:
                if word.startswith(prefix) and len(word) - len(prefix) >= 3:
                    expanded_words.add(word[len(prefix):])
            # add prefixed variants
            for prefix in hebrew_prefixes:
                expanded_words.add(prefix + word)

        if expanded_words:
            all_chunks = collection.get(
                where={"leaflet_id": leaflet_id},
                include=["documents", "metadatas"],
            )
            for doc, meta in zip(all_chunks["documents"], all_chunks["metadatas"]):
                if any(word in doc for word in expanded_words) and doc not in seen:
                    ranked.append({
                        "text":    doc,
                        "page":    meta.get("page", "?"),
                        "section": meta.get("section") or None,
                        "score":   0.3,
                    })

        return ranked[:n_results]

    except ChatbotError:
        raise
    except Exception as exc:
        raise ChatbotError(ErrorCode.VECTOR_DB_ERROR, detail=str(exc)) from exc


# Existence check 

def leaflet_exists(leaflet_id: str) -> bool:
    try:
        collection = _get_collection()
        results = collection.get(where={"leaflet_id": leaflet_id}, limit=1)
        return len(results["ids"]) > 0
    except Exception:
        return False


# Delete

def delete_leaflet(leaflet_id: str) -> bool:
    try:
        collection = _get_collection()
        existing = collection.get(where={"leaflet_id": leaflet_id})
        if not existing["ids"]:
            return False
        collection.delete(ids=existing["ids"])
        log.info("Deleted leaflet vectors", extra={"leaflet_id": leaflet_id, "chunks_deleted": len(existing["ids"])})
        return True
    except Exception as exc:
        log.warning("Failed to delete leaflet vectors", extra={"leaflet_id": leaflet_id, "error": str(exc)})
        return False