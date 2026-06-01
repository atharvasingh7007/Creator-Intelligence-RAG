"""
Qdrant vector store service.

Handles collection management, upsert, search, and fingerprint dedup.
"""

import hashlib
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)
from app.config import get_settings
from app.models.video import VideoChunk
from app.monitoring.logger import get_logger

logger = get_logger(__name__)

_client: QdrantClient | None = None


def get_qdrant_client() -> QdrantClient:
    """Singleton Qdrant client."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = QdrantClient(
            host=settings.qdrant_host, port=settings.qdrant_port
        )
        logger.info(
            f"Connected to Qdrant at {settings.qdrant_host}:{settings.qdrant_port}"
        )
    return _client


def ensure_collection():
    """Create the video_chunks collection if it doesn't exist."""
    settings = get_settings()
    client = get_qdrant_client()

    collections = [c.name for c in client.get_collections().collections]
    if settings.qdrant_collection not in collections:
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(
                size=settings.embedding_dim,
                distance=Distance.COSINE,
            ),
        )
        logger.info(f"Created collection: {settings.qdrant_collection}")
    else:
        logger.info(f"Collection exists: {settings.qdrant_collection}")


def upsert_chunks(
    chunks: list[VideoChunk],
    embeddings: list[list[float]],
):
    """Store chunks with embeddings in Qdrant."""
    settings = get_settings()
    client = get_qdrant_client()

    points = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        # Deterministic int ID using MD5
        chunk_hash = int(hashlib.md5(chunk.chunk_id.encode()).hexdigest(), 16)
        point = PointStruct(
            id=chunk_hash % (2**63 - 1),  # Max safe int for Qdrant ID
            vector=embedding,
            payload={
                "chunk_id": chunk.chunk_id,
                "video_id": chunk.video_id,
                "text": chunk.text,
                "timestamp": chunk.timestamp,
                "chunk_index": chunk.chunk_index,
            },
        )
        points.append(point)

    # Batch upsert
    batch_size = 100
    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]
        client.upsert(
            collection_name=settings.qdrant_collection,
            points=batch,
        )

    logger.info(f"Upserted {len(points)} chunks for video")


def search_similar(
    query_embedding: list[float],
    video_ids: list[str] | None = None,
    top_k: int = 20,
) -> list[dict]:
    """
    Search for similar chunks by embedding.

    Args:
        query_embedding: 384-dim query vector
        video_ids: Optional filter to specific videos
        top_k: Number of results (default 20 for reranking)

    Returns:
        List of dicts with chunk data and scores
    """
    settings = get_settings()
    client = get_qdrant_client()

    # Build filter if video_ids specified
    query_filter = None
    if video_ids:
        query_filter = Filter(
            should=[
                FieldCondition(
                    key="video_id", match=MatchValue(value=vid)
                )
                for vid in video_ids
            ]
        )

    results = client.search(
        collection_name=settings.qdrant_collection,
        query_vector=query_embedding,
        query_filter=query_filter,
        limit=top_k,
    )

    return [
        {
            "chunk_id": (hit.payload or {}).get("chunk_id", ""),
            "video_id": (hit.payload or {}).get("video_id", ""),
            "text": (hit.payload or {}).get("text", ""),
            "timestamp": (hit.payload or {}).get("timestamp", ""),
            "chunk_index": (hit.payload or {}).get("chunk_index", 0),
            "score": hit.score,
        }
        for hit in results
    ]


def delete_by_video_id(video_id: str):
    """Delete all chunks for a specific video."""
    settings = get_settings()
    client = get_qdrant_client()

    client.delete(
        collection_name=settings.qdrant_collection,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="video_id", match=MatchValue(value=video_id)
                )
            ]
        ),
    )
    logger.info(f"Deleted chunks for video {video_id}")
