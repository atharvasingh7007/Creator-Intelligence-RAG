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
        # Create a mapping from raw video ID to friendly label (A, B, C...)
        vid_to_label = {}
        for idx, (vid_id, _) in enumerate(metadata.items()):
            vid_to_label[vid_id] = f"Video {chr(65 + idx)}"
            
        def format_pair(pair_str: str) -> str:
            parts = pair_str.split("_vs_")
            if len(parts) == 2:
                l1 = vid_to_label.get(parts[0], parts[0])
                l2 = vid_to_label.get(parts[1], parts[1])
                return f"{l1} vs {l2}"
            return pair_str

        parts.append("=== Pre-Computed Analysis ===")
        parts.append(f"Hashtag Overlap (All Videos): {analysis.hashtag_overlap}")
        
        parts.append("Engagement Gaps (Pairwise):")
        for pair, gap in analysis.engagement_gaps.items():
            parts.append(f"  {format_pair(pair)}: {gap}")
            
        parts.append("Creator Size Ratios (Pairwise):")
        for pair, ratio in analysis.creator_size_ratios.items():
            parts.append(f"  {format_pair(pair)}: {ratio}x")
            
        parts.append("Duration Gaps (Pairwise):")
        for pair, gap in analysis.duration_gaps.items():
            parts.append(f"  {format_pair(pair)}: {gap}s")
            
        parts.append("Hook Similarities (Pairwise):")
        for pair, sim in analysis.hook_similarities.items():
            parts.append(f"  {format_pair(pair)}: {sim}")
            
        parts.append("Questions Count:")
        for vid, count in analysis.question_counts.items():
            parts.append(f"  {vid_to_label.get(vid, vid)}: {count}")
            
        parts.append("CTAs Count:")
        for vid, count in analysis.cta_counts.items():
            parts.append(f"  {vid_to_label.get(vid, vid)}: {count}")
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
