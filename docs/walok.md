# Build Walkthrough — Creator Intelligence RAG Platform

## What Was Built

A full-stack RAG-powered creator intelligence platform: **37 backend files** + **11 frontend files** + **3 infrastructure files**.

---

## Backend (Python / FastAPI)

### Infrastructure
| File | Purpose |
|---|---|
| [docker-compose.yml](file:///c:/Users/Atharva/Documents/rag/docker-compose.yml) | Qdrant (6333) + PostgreSQL (5432) |
| [requirements.txt](file:///c:/Users/Atharva/Documents/rag/backend/requirements.txt) | 17 dependencies |
| [.env.example](file:///c:/Users/Atharva/Documents/rag/backend/.env.example) | All config variables |

### Core Application
| File | Purpose |
|---|---|
| [main.py](file:///c:/Users/Atharva/Documents/rag/backend/app/main.py) | FastAPI app, lifespan, CORS, routers, health + metrics endpoints |
| [config.py](file:///c:/Users/Atharva/Documents/rag/backend/app/config.py) | Pydantic BaseSettings, all env vars |

### Models
| File | Purpose |
|---|---|
| [video.py](file:///c:/Users/Atharva/Documents/rag/backend/app/models/video.py) | VideoMetadata, VideoChunk, IngestionState |
| [chat.py](file:///c:/Users/Atharva/Documents/rag/backend/app/models/chat.py) | IntentType, AnalysisResult, Citation, ChatState |

### Services (11 files)
| File | Key Design Decision |
|---|---|
| [metadata_extractor.py](file:///c:/Users/Atharva/Documents/rag/backend/app/services/metadata_extractor.py) | SHA256 fingerprinting, engagement rate calc |
| [transcript_extractor.py](file:///c:/Users/Atharva/Documents/rag/backend/app/services/transcript_extractor.py) | Quality scoring (length adequacy + caption artifact density) |
| [chunker.py](file:///c:/Users/Atharva/Documents/rag/backend/app/services/chunker.py) | 400 tokens, 50 overlap, tiktoken, timestamp estimation |
| [embedder.py](file:///c:/Users/Atharva/Documents/rag/backend/app/services/embedder.py) | BGE small singleton, 384-dim, normalized |
| [vector_store.py](file:///c:/Users/Atharva/Documents/rag/backend/app/services/vector_store.py) | Qdrant HNSW cosine, batch upsert, filtered search |
| [llm.py](file:///c:/Users/Atharva/Documents/rag/backend/app/services/llm.py) | Gemini Flash, streaming + sync generation |
| [metadata_db.py](file:///c:/Users/Atharva/Documents/rag/backend/app/services/metadata_db.py) | PostgreSQL via SQLAlchemy async + asyncpg |
| [intent_router.py](file:///c:/Users/Atharva/Documents/rag/backend/app/services/intent_router.py) | **Hybrid**: keyword regex first, LLM fallback if ambiguous |
| [reranker.py](file:///c:/Users/Atharva/Documents/rag/backend/app/services/reranker.py) | BGE cross-encoder, 20→5, FP16, latency tracked |
| [analysis_engine.py](file:///c:/Users/Atharva/Documents/rag/backend/app/services/analysis_engine.py) | **All deterministic**: engagement_gap, hook_similarity, CTA count, question count, hashtag Jaccard |
| [memory.py](file:///c:/Users/Atharva/Documents/rag/backend/app/services/memory.py) | Summary compression, bounded (not buffer) |

### LangGraph Pipelines
| File | Flow |
|---|---|
| [ingestion_graph.py](file:///c:/Users/Atharva/Documents/rag/backend/app/graphs/ingestion_graph.py) | Fingerprint → Metadata → Transcript → Hook → Chunk → Embed → Store → Summary → Save (with failure paths) |
| [chat_graph.py](file:///c:/Users/Atharva/Documents/rag/backend/app/graphs/chat_graph.py) | Intent → Metadata → Conditional Retrieval → Rerank → Analyze → Citations → Memory → Generate |

### Prompt Templates (5 files)
| File | Intent |
|---|---|
| [system.py](file:///c:/Users/Atharva/Documents/rag/backend/app/prompts/system.py) | Base analyst role |
| [engagement.py](file:///c:/Users/Atharva/Documents/rag/backend/app/prompts/engagement.py) | Views, likes, rate |
| [comparison.py](file:///c:/Users/Atharva/Documents/rag/backend/app/prompts/comparison.py) | General video comparison |
| [hook_analysis.py](file:///c:/Users/Atharva/Documents/rag/backend/app/prompts/hook_analysis.py) | Hook/intro comparison |
| [creator_info.py](file:///c:/Users/Atharva/Documents/rag/backend/app/prompts/creator_info.py) | Creator/channel info |

### Monitoring
| File | Purpose |
|---|---|
| [logger.py](file:///c:/Users/Atharva/Documents/rag/backend/app/monitoring/logger.py) | Structured JSON logging |
| [metrics.py](file:///c:/Users/Atharva/Documents/rag/backend/app/monitoring/metrics.py) | Latency tracking decorator, counters, `/api/metrics` endpoint |

### API Routers
| File | Endpoints |
|---|---|
| [ingest.py](file:///c:/Users/Atharva/Documents/rag/backend/app/routers/ingest.py) | `POST /api/ingest`, `GET /api/videos`, `GET /api/videos/{id}` |
| [chat.py](file:///c:/Users/Atharva/Documents/rag/backend/app/routers/chat.py) | `POST /api/chat` (SSE), `POST /api/chat/sync`, `DELETE /api/chat/{sid}` |

---

## Frontend (Next.js + TypeScript + TailwindCSS)

| File | Purpose |
|---|---|
| [globals.css](file:///c:/Users/Atharva/Documents/rag/frontend/src/app/globals.css) | Premium dark theme, glassmorphism, 7 animation types, custom scrollbars |
| [layout.tsx](file:///c:/Users/Atharva/Documents/rag/frontend/src/app/layout.tsx) | Inter font, SEO metadata |
| [page.tsx](file:///c:/Users/Atharva/Documents/rag/frontend/src/app/page.tsx) | Split layout: collapsible sidebar + chat panel |
| [ChatInterface.tsx](file:///c:/Users/Atharva/Documents/rag/frontend/src/components/ChatInterface.tsx) | SSE streaming, typing dots, intent badges, suggestion pills |
| [VideoIngest.tsx](file:///c:/Users/Atharva/Documents/rag/frontend/src/components/VideoIngest.tsx) | URL input, platform detection, quality feedback |
| [VideoCard.tsx](file:///c:/Users/Atharva/Documents/rag/frontend/src/components/VideoCard.tsx) | Metric grid, selection toggle, quality badge |
| [ComparisonDashboard.tsx](file:///c:/Users/Atharva/Documents/rag/frontend/src/components/ComparisonDashboard.tsx) | Side-by-side bars, winner highlighting, hashtag Jaccard |
| [CitationBlock.tsx](file:///c:/Users/Atharva/Documents/rag/frontend/src/components/CitationBlock.tsx) | Source cards with index, timestamp, snippet |
| [api.ts](file:///c:/Users/Atharva/Documents/rag/frontend/src/lib/api.ts) | Full API client with SSE async generator |
| [types.ts](file:///c:/Users/Atharva/Documents/rag/frontend/src/lib/types.ts) | TypeScript interfaces matching backend models |

---

## Verification

| Check | Result |
|---|---|
| Frontend `next build` | ✅ Compiled successfully, 0 errors |
| TypeScript | ✅ Passed in 2.4s |
| Static generation | ✅ 4/4 pages generated |
| Project structure | ✅ 50+ files, clean layout |

---

## v3 Corrections Implemented

| Correction | Status |
|---|---|
| No semantic cache in implementation | ✅ Removed (documented in future improvements) |
| No hook_strength scoring | ✅ Removed (hook_text stored, LLM compares, hook_similarity kept) |
| No sentiment scoring | ✅ Replaced with question_count + cta_count |
| Transcript quality score | ✅ Computed during ingestion, flagged in context |
| Observability module | ✅ Structured JSON logger + metrics + `/api/metrics` endpoint |
| LangGraph failure paths | ✅ Conditional edges for transcript/metadata failure + fallback node |

---

## How to Run

```bash
# 1. Start infrastructure
docker-compose up -d

# 2. Backend
cd backend
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # Add GEMINI_API_KEY
uvicorn app.main:app --reload --port 8000

# 3. Frontend
cd frontend
npm run dev
```

Then open http://localhost:3000
