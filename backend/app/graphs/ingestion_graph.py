"""
LangGraph Ingestion Pipeline.

Flow:
  START → check_fingerprint → extract_metadata → extract_transcript
  → extract_hook → chunk_transcript → generate_embeddings
  → store_vectors → generate_summary → store_metadata → END

Includes failure paths for transcript and metadata extraction.
LangGraph shines when showing conditional recovery.
"""

from typing import TypedDict, Annotated, Any
from langgraph.graph import StateGraph, END  # type: ignore

from app.services.metadata_extractor import (
    extract_metadata as _extract_metadata,
    compute_video_hash,
)
from app.services.transcript_extractor import (
    extract_transcript as _extract_transcript,
    extract_hook,
)
from app.services.chunker import chunk_transcript as _chunk_transcript
from app.services.embedder import embed_texts
from app.services.vector_store import upsert_chunks, ensure_collection
from app.services.llm import generate_summary as _generate_summary
from app.services.metadata_db import check_fingerprint, get_video_by_hash, save_video, check_fingerprint_with_ttl
from app.monitoring.logger import get_logger
from app.monitoring.metrics import increment_counter, record_latency
import time

logger = get_logger(__name__)


class IngestionState(TypedDict):
    """State passed through the ingestion graph."""

    url: str
    video_hash: str
    already_exists: bool
    metadata: dict | None
    transcript: str
    transcript_quality: float
    hook_text: str
    chunks: list[dict]
    embeddings: list[list[float]]
    summary: str
    error: str | None
    status: str
    needs_refresh: bool


# --- Graph Nodes ---


async def check_fingerprint_node(state: IngestionState) -> dict:
    """Check if video was already ingested and whether metadata is stale."""
    video_hash = compute_video_hash(state["url"])
    exists, needs_refresh = await check_fingerprint_with_ttl(video_hash)

    if exists and not needs_refresh:
        # Fresh — skip entirely
        existing_meta = await get_video_by_hash(video_hash)
        logger.info(f"Video {video_hash[:12]} already ingested and fresh")
        return {
            "video_hash": video_hash,
            "already_exists": True,
            "needs_refresh": False,
            "metadata": existing_meta.model_dump() if existing_meta else None,
            "status": "already_exists",
            "error": "Already ingested — no duplicate processing",
        }

    if exists and needs_refresh:
        # Stale — need metadata refresh only (no re-embedding)
        existing_meta = await get_video_by_hash(video_hash)
        logger.info(f"Video {video_hash[:12]} exists but metadata is stale — refreshing")
        return {
            "video_hash": video_hash,
            "already_exists": True,
            "needs_refresh": True,
            "metadata": existing_meta.model_dump() if existing_meta else None,
            "status": "needs_refresh",
        }

    return {"video_hash": video_hash, "already_exists": False, "needs_refresh": False}


async def extract_metadata_node(state: IngestionState) -> dict:
    """Extract video metadata via yt-dlp."""
    try:
        metadata = await _extract_metadata(state["url"])
        metadata.video_hash = state["video_hash"]
        return {"metadata": metadata.model_dump(), "status": "metadata_ok"}
    except Exception as e:
        logger.error(f"Metadata extraction failed: {e}")
        return {"error": f"Metadata extraction failed: {str(e)}", "status": "failed"}


async def extract_transcript_node(state: IngestionState) -> dict:
    """Extract transcript with quality scoring."""
    duration = state.get("metadata", {}).get("duration", 0) if state.get("metadata") else 0

    try:
        transcript, quality = await _extract_transcript(
            state["url"], duration_seconds=duration
        )

        if not transcript:
            logger.warning("Empty transcript — video may lack captions")
            return {
                "transcript": "",
                "transcript_quality": 0.0,
                "error": "Transcript unavailable",
                "status": "transcript_failed",
            }

        return {
            "transcript": transcript,
            "transcript_quality": quality,
            "status": "transcript_ok",
        }
    except Exception as e:
        logger.error(f"Transcript extraction failed: {e}")
        return {
            "transcript": "",
            "transcript_quality": 0.0,
            "error": f"Transcript extraction failed: {str(e)}",
            "status": "transcript_failed",
        }


async def extract_hook_node(state: IngestionState) -> dict:
    """Extract hook text (first 50 words)."""
    hook = extract_hook(state.get("transcript", ""))
    return {"hook_text": hook}


async def chunk_transcript_node(state: IngestionState) -> dict:
    """Chunk transcript into 400-token overlapping segments."""
    transcript = state.get("transcript", "")
    if not transcript:
        return {"chunks": []}

    metadata = state.get("metadata") or {}
    video_id = metadata.get("video_id", state["video_hash"][:12])
    duration = metadata.get("duration", 0)

    chunks = _chunk_transcript(transcript, video_id, duration)
    return {"chunks": [c.model_dump() for c in chunks]}


async def generate_embeddings_node(state: IngestionState) -> dict:
    """Generate BGE embeddings for all chunks."""
    chunks = state.get("chunks", [])
    if not chunks:
        return {"embeddings": []}

    texts = [c["text"] for c in chunks]
    embeddings = embed_texts(texts)

    logger.info(f"Generated {len(embeddings)} embeddings (384-dim)")
    return {"embeddings": embeddings}


async def store_vectors_node(state: IngestionState) -> dict:
    """Store chunk embeddings in Qdrant."""
    chunks = state.get("chunks", [])
    embeddings = state.get("embeddings", [])

    if not chunks or not embeddings:
        return {}

    ensure_collection()

    from app.models.video import VideoChunk

    chunk_objects = [VideoChunk(**c) for c in chunks]
    upsert_chunks(chunk_objects, embeddings)

    logger.info(f"Stored {len(chunks)} chunks in Qdrant")
    return {}


async def generate_summary_node(state: IngestionState) -> dict:
    """Generate summary AFTER chunking (enables future chunk-level summaries)."""
    transcript = state.get("transcript", "")
    if not transcript:
        return {"summary": ""}

    summary = await _generate_summary(transcript)
    return {"summary": summary}


async def store_metadata_node(state: IngestionState) -> dict:
    """Store final metadata in PostgreSQL."""
    metadata_dict = state.get("metadata")
    if not metadata_dict:
        return {"status": "failed", "error": "No metadata to store"}

    from app.models.video import VideoMetadata

    metadata = VideoMetadata(**metadata_dict)
    metadata.hook_text = state.get("hook_text", "")
    metadata.summary = state.get("summary", "")
    metadata.transcript_quality = state.get("transcript_quality", 1.0)

    await save_video(metadata)
    increment_counter("ingestion_count")

    logger.info(f"Ingestion complete: {metadata.title}")
    return {"status": "success"}


async def fallback_node(state: IngestionState) -> dict:
    """Fallback for transcript failure — store metadata without transcript."""
    logger.warning("Running fallback: storing metadata without transcript data")

    metadata_dict = state.get("metadata")
    if metadata_dict:
        from app.models.video import VideoMetadata

        metadata = VideoMetadata(**metadata_dict)
        metadata.transcript_quality = 0.0
        metadata.summary = "Transcript unavailable for this video."
        await save_video(metadata)
        increment_counter("ingestion_count")
        return {"status": "partial_success"}

    return {"status": "failed"}


async def refresh_metadata_node(state: IngestionState) -> dict:
    """Re-fetch metadata from yt-dlp for a stale video.

    Only updates engagement metrics and metadata — skips transcript,
    chunking, and embedding since the content hasn't changed.
    """
    try:
        fresh_metadata = await _extract_metadata(state["url"])
        fresh_metadata.video_hash = state["video_hash"]

        # Preserve existing transcript-derived fields from old metadata
        old_meta = state.get("metadata") or {}
        fresh_metadata.hook_text = old_meta.get("hook_text", "")
        fresh_metadata.summary = old_meta.get("summary", "")
        fresh_metadata.transcript_quality = old_meta.get("transcript_quality", 1.0)

        await save_video(fresh_metadata)
        logger.info(
            f"Refreshed metadata for '{fresh_metadata.title}' "
            f"(views: {fresh_metadata.views}, engagement: {fresh_metadata.engagement_rate}%)"
        )
        return {
            "metadata": fresh_metadata.model_dump(),
            "status": "refreshed",
        }
    except Exception as e:
        logger.error(f"Metadata refresh failed: {e}")
        return {"status": "refresh_failed", "error": str(e)}


# --- Routing Functions ---


def should_continue_after_fingerprint(state: IngestionState) -> str:
    """Route: skip if fresh, refresh if stale, full pipeline if new."""
    if state.get("already_exists") and not state.get("needs_refresh"):
        return "end"
    if state.get("already_exists") and state.get("needs_refresh"):
        return "refresh_metadata"
    return "extract_metadata"


def should_continue_after_metadata(state: IngestionState) -> str:
    """Route: continue if metadata OK, end if failed."""
    if state.get("status") == "failed":
        return "end"
    return "extract_transcript"


def should_continue_after_transcript(state: IngestionState) -> str:
    """Route: continue if transcript OK, fallback if failed."""
    if state.get("status") == "transcript_failed":
        return "fallback"
    return "extract_hook"


# --- Build Graph ---


def build_ingestion_graph() -> StateGraph:
    """Build the LangGraph ingestion pipeline with failure paths."""

    graph = StateGraph(IngestionState)

    # Add nodes
    graph.add_node("check_fingerprint", check_fingerprint_node)
    graph.add_node("extract_metadata", extract_metadata_node)
    graph.add_node("extract_transcript", extract_transcript_node)
    graph.add_node("extract_hook", extract_hook_node)
    graph.add_node("chunk_transcript", chunk_transcript_node)
    graph.add_node("generate_embeddings", generate_embeddings_node)
    graph.add_node("store_vectors", store_vectors_node)
    graph.add_node("generate_summary", generate_summary_node)
    graph.add_node("store_metadata", store_metadata_node)
    graph.add_node("fallback", fallback_node)
    graph.add_node("refresh_metadata", refresh_metadata_node)

    # Set entry point
    graph.set_entry_point("check_fingerprint")

    # Conditional edges (failure paths)
    graph.add_conditional_edges(
        "check_fingerprint",
        should_continue_after_fingerprint,
        {
            "extract_metadata": "extract_metadata",
            "refresh_metadata": "refresh_metadata",
            "end": END,
        },
    )

    graph.add_conditional_edges(
        "extract_metadata",
        should_continue_after_metadata,
        {"extract_transcript": "extract_transcript", "end": END},
    )

    graph.add_conditional_edges(
        "extract_transcript",
        should_continue_after_transcript,
        {"extract_hook": "extract_hook", "fallback": "fallback"},
    )

    # Happy path edges
    graph.add_edge("extract_hook", "chunk_transcript")
    graph.add_edge("chunk_transcript", "generate_embeddings")
    graph.add_edge("generate_embeddings", "store_vectors")
    graph.add_edge("store_vectors", "generate_summary")
    graph.add_edge("generate_summary", "store_metadata")
    graph.add_edge("store_metadata", END)

    # Fallback ends
    graph.add_edge("fallback", END)

    # Refresh path ends
    graph.add_edge("refresh_metadata", END)

    return graph.compile()


# Compiled graph singleton
ingestion_graph = build_ingestion_graph()


async def run_ingestion(url: str) -> dict:
    """Run the full ingestion pipeline for a video URL."""
    start = time.perf_counter()

    initial_state: IngestionState = {
        "url": url,
        "video_hash": "",
        "already_exists": False,
        "metadata": None,
        "transcript": "",
        "transcript_quality": 1.0,
        "hook_text": "",
        "chunks": [],
        "embeddings": [],
        "summary": "",
        "error": None,
        "status": "pending",
        "needs_refresh": False,
    }

    result = await ingestion_graph.ainvoke(initial_state)

    latency_ms = (time.perf_counter() - start) * 1000
    record_latency("ingestion_latency_ms", latency_ms)

    logger.info(
        f"Ingestion completed: status={result.get('status')} "
        f"latency={latency_ms:.0f}ms"
    )
    return result
