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
    videos: list[VideoMetadata],
    transcripts: dict[str, str] = None,
) -> AnalysisResult:
    """
    Compute deterministic analysis metrics between N videos.
    Every metric is explainable and defensible in an interview.
    """
    transcripts = transcripts or {}
    
    # N-way hashtag overlap (Jaccard-ish)
    tag_sets = [set(h.lower() for h in v.hashtags) for v in videos]
    if tag_sets:
        intersection = tag_sets[0].intersection(*tag_sets[1:])
        union = tag_sets[0].union(*tag_sets[1:])
        hashtag_overlap = round(len(intersection) / len(union), 4) if union else 0.0
    else:
        hashtag_overlap = 0.0

    engagement_gaps = {}
    creator_size_ratios = {}
    duration_gaps = {}
    hook_similarities = {}
    question_counts = {}
    cta_counts = {}

    for v in videos:
        txt = transcripts.get(v.video_id, "")
        question_counts[v.video_id] = _count_questions(txt)
        cta_counts[v.video_id] = _count_ctas(txt)

    for i in range(len(videos)):
        for j in range(i + 1, len(videos)):
            v1, v2 = videos[i], videos[j]
            pair_key = f"{v1.video_id}_vs_{v2.video_id}"
            
            engagement_gaps[pair_key] = round(abs(v1.engagement_rate - v2.engagement_rate), 4)
            
            f1 = max(v1.follower_count, 1)
            f2 = max(v2.follower_count, 1)
            creator_size_ratios[pair_key] = round(max(f1, f2) / min(f1, f2), 2)
            
            duration_gaps[pair_key] = abs(v1.duration - v2.duration)
            
            if v1.hook_text and v2.hook_text:
                try:
                    emb_a = embed_single(v1.hook_text)
                    emb_b = embed_single(v2.hook_text)
                    hook_similarities[pair_key] = _cosine_similarity(emb_a, emb_b)
                except Exception as e:
                    logger.warning(f"Hook similarity computation failed: {e}")

    result = AnalysisResult(
        engagement_gaps=engagement_gaps,
        creator_size_ratios=creator_size_ratios,
        duration_gaps=duration_gaps,
        hook_similarities=hook_similarities,
        hashtag_overlap=hashtag_overlap,
        question_counts=question_counts,
        cta_counts=cta_counts,
    )

    logger.info(
        f"Analysis computed for {len(videos)} videos: "
        f"hashtag_overlap={hashtag_overlap}"
    )
    return result
