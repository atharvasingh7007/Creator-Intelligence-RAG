"""
Video and chunk data models.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone


class VideoMetadata(BaseModel):
    """Metadata for an ingested video."""

    video_id: str
    video_hash: str  # sha256(url) for fingerprinting / dedup
    url: str
    title: str
    creator_name: str
    views: int = 0
    likes: int = 0
    comments: int = 0
    follower_count: int = 0
    upload_date: str = ""
    hashtags: list[str] = Field(default_factory=list)
    duration: int = 0  # seconds
    engagement_rate: float = 0.0  # (likes+comments)/views * 100
    hook_text: str = ""  # first 50 words of transcript
    summary: str = ""
    platform: str = "youtube"  # "youtube" | "instagram"
    transcript_quality: float = 1.0  # 0.0–1.0 quality score
    ingested_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class VideoChunk(BaseModel):
    """A single chunk of a video transcript."""

    chunk_id: str  # e.g. "abc123_15"
    video_id: str
    text: str
    timestamp: str = ""  # estimated timestamp e.g. "00:04:30"
    chunk_index: int = 0


class IngestionRequest(BaseModel):
    """Request to ingest a video."""

    url: str


class IngestionResponse(BaseModel):
    """Response after ingestion completes."""

    video_id: str
    title: str
    status: str  # "success" | "already_exists" | "failed"
    message: str = ""
    transcript_quality: float = 1.0


class IngestionState(BaseModel):
    """LangGraph state for the ingestion pipeline."""

    url: str
    video_hash: str = ""
    already_exists: bool = False
    metadata: Optional[VideoMetadata] = None
    transcript: str = ""
    transcript_quality: float = 1.0
    hook_text: str = ""
    chunks: list[VideoChunk] = Field(default_factory=list)
    embeddings: list[list[float]] = Field(default_factory=list)
    summary: str = ""
    error: Optional[str] = None
    status: str = "pending"
