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

    engagement_gaps: dict[str, float] = Field(default_factory=dict)  # "vid1_vs_vid2" -> gap
    creator_size_ratios: dict[str, float] = Field(default_factory=dict)
    duration_gaps: dict[str, int] = Field(default_factory=dict)
    hook_similarities: dict[str, float] = Field(default_factory=dict)
    hashtag_overlap: float = 0.0  # N-way overlap
    question_counts: dict[str, int] = Field(default_factory=dict)  # vid -> count
    cta_counts: dict[str, int] = Field(default_factory=dict)  # vid -> count


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
