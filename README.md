# Creator Intelligence RAG Platform

A scalable creator-intelligence platform powered by Retrieval-Augmented Generation (RAG). Ingest YouTube videos, extract transcripts and metadata, compute engagement analytics, and perform conversational analysis through a streaming chat interface.

## Why Not Pure RAG?

Most RAG systems perform:

```
Query → Retrieve → Generate
```

This system performs:

```
Query → Intent Routing → Metadata Retrieval → Transcript Retrieval
→ Reranking → Structured Analysis → Generation
```

This reduces hallucinations and improves comparative reasoning because the LLM receives **pre-computed analytical signals** (engagement deltas, hook similarity, CTA counts, hashtag overlap) instead of inferring everything from raw transcript chunks.

---

## Architecture

```
                     USER
                       │
                       ▼
              Next.js Frontend
                       │
                       ▼
                 FastAPI API
                       │
                       ▼
                 LangGraph
         ┌──────────┼──────────┐
         ▼          ▼          ▼
     Metadata   Retrieval   Analysis
         │          │          │
         ▼          ▼          ▼
    PostgreSQL   Qdrant     Reasoning
         │          │
         └──────┬───┘
                ▼
          Gemini Flash
                ▼
        Streaming Response
```

### Key Architectural Decisions

| Decision | Rationale |
|---|---|
| **PostgreSQL** (not SQLite) | Better concurrency, production credibility |
| **BGE Small** embeddings | Open source, zero cost, strong retrieval quality |
| **BGE Reranker** | Cross-encoder quality boost: 20 candidates → top 5 |
| **Hybrid Intent Router** | Keyword-first (free, instant), LLM fallback only when ambiguous |
| **Video Fingerprinting** | SHA256 deduplication prevents re-embedding, re-transcription |
| **Summary after Chunking** | Enables future multi-level retrieval (chunk + video summaries) |
| **Metadata before Retrieval** | Structured data always available; vector search only when needed |
| **Deterministic Analysis** | Every metric is explainable: engagement_gap, hook_similarity, CTA counts |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js + React + TailwindCSS |
| Backend | FastAPI (Python, async) |
| Orchestration | LangGraph |
| Embeddings | BAAI/bge-small-en-v1.5 (384-dim) |
| Reranker | BAAI/bge-reranker-v2-m3 |
| Vector DB | Qdrant (HNSW, cosine) |
| LLM | Gemini Flash |
| Metadata DB | PostgreSQL |

---

## Quick Start

### 1. Start Infrastructure

```bash
docker-compose up -d
```

This starts Qdrant (port 6333) and PostgreSQL (port 5432).

### 2. Setup Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your GEMINI_API_KEY
```

### 3. Run Backend

```bash
uvicorn app.main:app --reload --port 8000
```

### 4. Ingest Videos

```bash
curl -X POST http://localhost:8000/api/ingest \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtube.com/watch?v=VIDEO_ID"}'
```

### 5. Chat

```bash
curl -X POST http://localhost:8000/api/chat/sync \
  -H "Content-Type: application/json" \
  -d '{"query": "Compare the engagement rates", "video_ids": ["id1", "id2"]}'
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/ingest` | Ingest a video URL |
| `GET` | `/api/videos` | List all ingested videos |
| `GET` | `/api/videos/{id}` | Get video metadata |
| `POST` | `/api/chat` | SSE streaming chat |
| `POST` | `/api/chat/sync` | Non-streaming chat |
| `DELETE` | `/api/chat/{session_id}` | Clear session memory |
| `GET` | `/api/metrics` | Pipeline metrics |
| `GET` | `/` | Health check |

---

## Analysis Metrics

Every metric is deterministic and defensible:

```json
{
  "engagement_gap": 4.2,
  "creator_size_ratio": 3.4,
  "duration_gap": 85,
  "hook_similarity": 0.72,
  "hashtag_overlap": 0.61,
  "question_count_a": 7,
  "question_count_b": 2,
  "cta_count_a": 4,
  "cta_count_b": 1
}
```

---

## LangGraph Pipelines

### Ingestion Graph (with failure paths)

```
START → Check Fingerprint → Extract Metadata → Extract Transcript
  ↓ (exists)                  ↓ (failed)         ↓ (failed)
 END                         END              Fallback (store metadata only)
                                                    ↓
→ Extract Hook → Chunk → Embed → Store Qdrant → Summary → Store Metadata → END
```

### Chat Graph

```
START → Hybrid Intent Router → Retrieve Metadata → Conditional Retrieval
→ Rerank → Structured Analysis → Citations → Memory → Streaming LLM → END
```

---

## Environment Variables

```
GEMINI_API_KEY=         # Google AI API key
QDRANT_HOST=localhost
QDRANT_PORT=6333
POSTGRES_URL=postgresql+asyncpg://rag:ragpassword@localhost:5432/rag_platform
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
CHUNK_SIZE=400
CHUNK_OVERLAP=50
```

---

## Cost Optimization

| Component | Cost |
|---|---|
| Embeddings (BGE) | $0 — local inference |
| Reranking (BGE) | $0 — local inference |
| Vector DB (Qdrant) | $0 — self-hosted |
| Transcript API | $0 — youtube-transcript-api |
| Video Fingerprinting | Prevents re-processing |
| LLM (Gemini Flash) | Only component with API cost |

---

## Future Improvements

- Hybrid BM25 + Dense Retrieval
- Redis Semantic Cache (20-40% LLM cost savings)
- Multi-Level Retrieval (chunk + video summaries)
- Agentic Retrieval
- Multi-Video Group Analysis
- Creator Performance Forecasting
- Horizontal worker scaling
- Multi-node Qdrant + Kubernetes
