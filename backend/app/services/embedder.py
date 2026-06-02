"""
BGE Embedding service.

Model: BAAI/bge-small-en-v1.5
Dimension: 384
Loaded once at startup via singleton pattern.
"""

from sentence_transformers import SentenceTransformer
from app.config import get_settings
from app.monitoring.logger import get_logger

logger = get_logger(__name__)

_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    """Singleton loader for the embedding model."""
    global _model
    if _model is None:
        settings = get_settings()
        logger.info(f"Loading embedding model: {settings.embedding_model}")
        _model = SentenceTransformer(settings.embedding_model)
        logger.info("Embedding model loaded successfully")
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings for a batch of texts.

    Returns list of 384-dim float vectors.
    """
    if not texts:
        return []

    model = get_embedding_model()
    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
        batch_size=32,
    )
    return embeddings.tolist()


def embed_single(text: str) -> list[float]:
    """Generate embedding for a single text."""
    results = embed_texts([text])
    return results[0] if results else []
