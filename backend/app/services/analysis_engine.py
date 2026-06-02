"""
Deterministic analysis engine.

Computes structured reasoning features that the LLM receives
instead of inferring everything from raw chunks.

All metrics are explainable and deterministic — no subjective scoring.
"""

import re
from app.models.video import VideoMetadata
from app.models.chat import AnalysisResult
from app.services.embedder import embed_single
from app.monitoring.logger import get_logger

logger = get_logger(__name__)

# Common CTA patterns in social media transcripts
CTA_PATTERNS = [
    r"\bsubscribe\b",
    r"\blike\b.*\bvideo\b",
    r"\bfollow\b",
    r"\bcomment\b.*\bbelow\b",
    r"\bshare\b",
    r"\bcheck\s+out\b",
    r"\blink\b.*\b(bio|description)\b",
    r"\bturn\s+on\b.*\bnotification",
    r"\bhit\s+the\b.*\b(bell|like)\b",
    r"\blet\s+me\s+know\b",
    r"\bsign\s+up\b",
    r"\bdownload\b",
]


def _count_questions(text: str) -> int:
    """Count question marks in transcript."""
    return text.count("?")


def _count_ctas(text: str) -> int:
    """Count calls-to-action using pattern matching."""
    text_lower = text.lower()
    return sum(
        1 for pattern in CTA_PATTERNS if re.search(pattern, text_lower)
    )


def _jaccard_similarity(set_a: set, set_b: set) -> float:
    """Jaccard similarity: |intersection| / |union|"""
    if not set_a and not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return round(len(intersection) / len(union), 4) if union else 0.0


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not vec_a or not vec_b:
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return round(dot / (norm_a * norm_b), 4)


def compute_analysis(
    video_a: VideoMetadata,
    video_b: VideoMetadata,
    transcript_a: str = "",
    transcript_b: str = "",
) -> AnalysisResult:
    """
    Compute deterministic analysis metrics between two videos.

    Every metric is explainable and defensible in an interview.
    """
    # Engagement gap
    engagement_gap = round(
        video_a.engagement_rate - video_b.engagement_rate, 4
    )

    # Creator size ratio (larger / smaller)
    fa = max(video_a.follower_count, 1)
    fb = max(video_b.follower_count, 1)
    creator_size_ratio = round(max(fa, fb) / min(fa, fb), 2)

    # Duration gap
    duration_gap = video_a.duration - video_b.duration

    # Hook similarity (cosine similarity of hook embeddings)
    hook_similarity = 0.0
    if video_a.hook_text and video_b.hook_text:
        try:
            emb_a = embed_single(video_a.hook_text)
            emb_b = embed_single(video_b.hook_text)
            hook_similarity = _cosine_similarity(emb_a, emb_b)
        except Exception as e:
            logger.warning(f"Hook similarity computation failed: {e}")

    # Hashtag overlap (Jaccard)
    hashtag_overlap = _jaccard_similarity(
        set(h.lower() for h in video_a.hashtags),
        set(h.lower() for h in video_b.hashtags),
    )

    # Question count
    question_count_a = _count_questions(transcript_a)
    question_count_b = _count_questions(transcript_b)

    # CTA count
    cta_count_a = _count_ctas(transcript_a)
    cta_count_b = _count_ctas(transcript_b)

    result = AnalysisResult(
        engagement_gap=engagement_gap,
        creator_size_ratio=creator_size_ratio,
        duration_gap=duration_gap,
        hook_similarity=hook_similarity,
        hashtag_overlap=hashtag_overlap,
        question_count_a=question_count_a,
        question_count_b=question_count_b,
        cta_count_a=cta_count_a,
        cta_count_b=cta_count_b,
    )

    logger.info(
        f"Analysis computed: engagement_gap={engagement_gap}, "
        f"hook_sim={hook_similarity}, hashtag_overlap={hashtag_overlap}"
    )
    return result
