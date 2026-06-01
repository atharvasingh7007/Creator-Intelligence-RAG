"""
Chat and analysis data models.
"""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class IntentType(str, Enum):
    """Supported query intents."""

    ENGAGEMENT = "engagement"
    CREATOR_INFO = "creator_info"
    HOOK_COMPARISON = "hook_comparison"
    GENERAL_COMPARISON = "general_comparison"


class AnalysisResult(BaseModel):
    """Deterministic analysis metrics — every field is explainable."""

    engagement_gap: float = 0.0  # engagement rate difference
    creator_size_ratio: float = 0.0  # follower count ratio
    duration_gap: int = 0  # seconds difference
    hook_similarity: float = 0.0  # cosine similarity of hook embeddings
    hashtag_overlap: float = 0.0  # Jaccard similarity of hashtag sets
    question_count_a: int = 0  # questions in video A transcript
    question_count_b: int = 0  # questions in video B transcript
    cta_count_a: int = 0  # calls-to-action in video A
    cta_count_b: int = 0  # calls-to-action in video B


class Citation(BaseModel):
    """Source reference for a claim in the response."""

    video_name: str
    chunk_id: str
    timestamp: str
    text_snippet: str


class ChatRequest(BaseModel):
    """Incoming chat request."""

    query: str
    session_id: str = "default"
    video_ids: list[str] = Field(default_factory=list)


class ChatState(BaseModel):
    """LangGraph state for the chat pipeline."""

    query: str
    session_id: str = "default"
    video_ids: list[str] = Field(default_factory=list)
    intent: IntentType = IntentType.GENERAL_COMPARISON
    intent_confidence: float = 0.0
    metadata: dict = Field(default_factory=dict)  # video_id -> VideoMetadata dict
    retrieved_chunks: list[dict] = Field(default_factory=list)
    reranked_chunks: list[dict] = Field(default_factory=list)
    analysis: Optional[AnalysisResult] = None
    citations: list[Citation] = Field(default_factory=list)
    memory_summary: str = ""
    context: str = ""
    response: str = ""
    error: Optional[str] = None
