"""
Video ingestion API router.

Endpoints:
  POST /api/ingest — ingest a video URL
  GET  /api/videos — list all ingested videos
  GET  /api/videos/{video_id} — get single video metadata
"""

# pyrefly: ignore [missing-import]
from fastapi import APIRouter, HTTPException
from app.models.video import IngestionRequest, IngestionResponse
from app.graphs.ingestion_graph import run_ingestion
from app.services.metadata_db import list_videos, get_video
from app.monitoring.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["ingestion"])


@router.post("/ingest", response_model=IngestionResponse)
async def ingest_video(request: IngestionRequest):
    """
    Ingest a video URL through the full pipeline:
    fingerprint -> metadata -> transcript -> hook -> chunk -> embed -> store.
    """
    logger.info(f"Ingestion request: {request.url}")

    try:
        result = await run_ingestion(request.url, force_refresh=request.force_refresh)

        status = result.get("status", "failed")
        metadata = result.get("metadata") or {}

        # Issue 4 fix: already_exists exits early without setting transcript_quality
        # in state, so fall back to the stored metadata value.
        tq = result.get("transcript_quality")
        transcript_quality = (
            tq if tq is not None
            else metadata.get("transcript_quality", 0.0)
        )

        # Issues 3 & 8 fix: handle all possible statuses with meaningful messages.
        message_map = {
            "success": "Ingestion successful",
            "already_exists": "Already ingested - metadata is fresh",
            "refreshed": "Metadata refreshed with latest stats",
            "partial_success": "Ingested without transcript - metadata only",
            "refresh_failed": "Metadata refresh failed - showing cached data",
            "failed": "Ingestion failed",
        }
        message = result.get("error") or message_map.get(status, "")

        return IngestionResponse(
            video_id=metadata.get("video_id", ""),
            title=metadata.get("title", "Unknown"),
            status=status,
            message=message,
            transcript_quality=transcript_quality,
        )

    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/videos")
async def get_all_videos():
    """List all ingested videos with metadata."""
    try:
        videos = await list_videos()
        return {
            "count": len(videos),
            "videos": [v.model_dump() for v in videos],
        }
    except Exception as e:
        logger.error(f"Failed to list videos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/videos/{video_id}")
async def get_video_by_id(video_id: str):
    """Get metadata for a specific video."""
    try:
        video = await get_video(video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        return video.model_dump()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get video {video_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
