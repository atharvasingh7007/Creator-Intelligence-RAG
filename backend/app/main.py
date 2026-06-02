"""
Creator Intelligence RAG Platform — FastAPI Application

Main entry point. Handles:
- App initialization with lifespan events
- CORS middleware
- Router registration
- Model preloading (embedder, reranker)
- Health check & metrics endpoints
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import ingest, chat
from app.services.metadata_db import init_db
from app.services.vector_store import ensure_collection
from app.monitoring.logger import get_logger
from app.monitoring.metrics import get_metrics_summary

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("Starting Creator Intelligence RAG Platform...")

    # Initialize database
    await init_db()
    logger.info("PostgreSQL initialized")

    # Ensure Qdrant collection
    try:
        ensure_collection()
        logger.info("Qdrant collection ready")
    except Exception as e:
        logger.error(f"Qdrant connection failed: {e}")
        logger.warning("Qdrant unavailable — retrieval will fail")

    # Preload ML models (optional: uncomment for faster first query)
    # from app.services.embedder import get_embedding_model
    # from app.services.reranker import get_reranker
    # get_embedding_model()
    # get_reranker()

    logger.info("Platform ready")
    yield

    logger.info("Shutting down...")


app = FastAPI(
    title="Creator Intelligence RAG Platform",
    description=(
        "A scalable creator-intelligence platform powered by RAG. "
        "Ingests YouTube videos, extracts transcripts and metadata, "
        "computes engagement analytics, and provides conversational "
        "analysis through a streaming chat interface."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(ingest.router)
app.include_router(chat.router)


@app.get("/")
async def root():
    """Health check."""
    return {
        "status": "healthy",
        "service": "Creator Intelligence RAG Platform",
        "version": "1.0.0",
    }


@app.get("/api/metrics")
async def metrics():
    """Pipeline metrics endpoint — observability."""
    return get_metrics_summary()
