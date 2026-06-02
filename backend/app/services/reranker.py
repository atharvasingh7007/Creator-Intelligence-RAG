"""
BGE Reranker service.

Model: BAAI/bge-reranker-v2-m3
Cross-encoder scoring: 20 candidates → top 5

Massive retrieval quality boost at minimal cost.
"""

from FlagEmbedding import FlagReranker
from app.config import get_settings
from app.monitoring.logger import get_logger
from app.monitoring.metrics import track_latency

logger = get_logger(__name__)

_reranker: FlagReranker | None = None


def get_reranker() -> FlagReranker:
    """Singleton reranker model."""
    global _reranker
    if _reranker is None:
        settings = get_settings()
        logger.info(f"Loading reranker model: {settings.reranker_model}")
        _reranker = FlagReranker(settings.reranker_model, use_fp16=True)
        logger.info("Reranker model loaded successfully")
    return _reranker


@track_latency("rerank")
def rerank_chunks(
    query: str,
    chunks: list[dict],
    top_k: int | None = None,
) -> list[dict]:
    """
    Rerank retrieved chunks using cross-encoder scoring.

    Args:
        query: User query
        chunks: List of chunk dicts from vector search (must have 'text' key)
        top_k: Number of top results to return (default from config: 5)

    Returns:
        Top-k chunks sorted by reranker score (descending)
    """
    settings = get_settings()
    top_k = top_k or settings.rerank_top_k

    if not chunks:
        return []

    if len(chunks) <= top_k:
        return chunks

    reranker = get_reranker()

    # Build query-passage pairs
    pairs = [[query, chunk["text"]] for chunk in chunks]

    # Score all pairs
    scores = reranker.compute_score(pairs, normalize=True)

    # Handle single result edge case
    if isinstance(scores, (float, int)):
        scores = [scores]

    # Attach scores and sort
    for chunk, score in zip(chunks, scores):
        chunk["rerank_score"] = float(score)

    ranked = sorted(chunks, key=lambda x: x.get("rerank_score", 0), reverse=True)

    logger.info(
        f"Reranked {len(chunks)} → top {top_k} "
        f"(best: {ranked[0]['rerank_score']:.3f})"
    )

    return ranked[:top_k]
