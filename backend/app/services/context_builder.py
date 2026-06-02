"""
Context builder.

Assembles structured context for the LLM from:
- Video metadata
- Retrieved/reranked chunks
- Analysis results
"""

from app.models.video import VideoMetadata
from app.models.chat import AnalysisResult, IntentType
from app.monitoring.logger import get_logger

logger = get_logger(__name__)


def build_context(
    intent: IntentType,
    metadata: dict[str, VideoMetadata],
    chunks: list[dict] | None = None,
    analysis: AnalysisResult | None = None,
) -> str:
    """
    Build structured context string for the LLM prompt.

    Adapts based on intent type:
    - engagement/creator_info: metadata only
    - hook_comparison: metadata + hooks
    - general_comparison: metadata + chunks + analysis
    """
    parts = []

    # Always include metadata
    # for vid_label, (vid_id, meta) in enumerate(metadata.items()):
    for vid_label, (_, meta) in enumerate(metadata.items()):
        label = chr(65 + vid_label)  # A, B, C...
        parts.append(f"=== Video {label}: {meta.title} ===")
        parts.append(f"Creator: {meta.creator_name}")
        parts.append(f"Views: {meta.views:,}")
        parts.append(f"Likes: {meta.likes:,}")
        parts.append(f"Comments: {meta.comments:,}")
        parts.append(f"Engagement Rate: {meta.engagement_rate}%")
        parts.append(f"Followers: {meta.follower_count:,}")
        parts.append(f"Duration: {meta.duration}s")
        parts.append(f"Hashtags: {', '.join(meta.hashtags[:10]) if meta.hashtags else 'None'}")
        parts.append(f"Platform: {meta.platform}")

        if meta.transcript_quality is not None and meta.transcript_quality < 0.6:
            parts.append(
                f"⚠ Transcript Quality: {meta.transcript_quality:.0%} "
                f"(answers may be less reliable)"
            )

        if intent in (IntentType.HOOK_COMPARISON, IntentType.GENERAL_COMPARISON):
            parts.append(f"Hook: {meta.hook_text or 'N/A'}")

        if meta.summary:
            parts.append(f"Summary: {meta.summary}")

        parts.append("")

    # Include analysis for comparison intents
    if analysis:
        parts.append("=== Pre-Computed Analysis ===")
        parts.append(f"Engagement Gap: {analysis.engagement_gap}")
        parts.append(f"Creator Size Ratio: {analysis.creator_size_ratio}x")
        parts.append(f"Duration Difference: {analysis.duration_gap}s")
        parts.append(f"Hook Similarity: {analysis.hook_similarity}")
        parts.append(f"Hashtag Overlap: {analysis.hashtag_overlap}")
        parts.append(f"Questions (A/B): {analysis.question_count_a}/{analysis.question_count_b}")
        parts.append(f"CTAs (A/B): {analysis.cta_count_a}/{analysis.cta_count_b}")
        parts.append("")

    # Include retrieved transcript chunks
    if chunks and intent in (
        IntentType.HOOK_COMPARISON,
        IntentType.GENERAL_COMPARISON,
    ):
        parts.append("=== Relevant Transcript Evidence ===")
        for i, chunk in enumerate(chunks, 1):
            vid_id = chunk.get("video_id", "?")
            timestamp = chunk.get("timestamp", "")
            chunk_id = chunk.get("chunk_id", "")
            text = chunk.get("text", "")
            score = float(chunk.get("rerank_score", chunk.get("score", 0)) or 0)
            parts.append(
                f"[{i}] Video: {vid_id} | Chunk: {chunk_id} | "
                f"Time: {timestamp} | Score: {score:.3f}"
            )
            parts.append(f"    {text[:300]}")
            parts.append("")

    context = "\n".join(parts)
    logger.info(f"Built context: {len(context)} chars for intent {intent.value}")
    return context
