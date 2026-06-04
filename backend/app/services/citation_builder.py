"""
Citation builder.

Attaches source references to each chunk used in the response.
Format: Video Name | Chunk ID | Timestamp | Snippet
"""

from app.models.chat import Citation
from app.monitoring.logger import get_logger

logger = get_logger(__name__)


def build_citations(
    chunks: list[dict],
    metadata: dict,  # video_id -> VideoMetadata
) -> list[Citation]:
    """
    Build citation objects from reranked chunks.

    Each citation references the source video, chunk, timestamp,
    and a text snippet for transparency.
    """
    citations = []
    seen_chunks = set()

    for chunk in chunks:
        chunk_id = chunk.get("chunk_id", "")
        if chunk_id in seen_chunks:
            continue
        seen_chunks.add(chunk_id)

        video_id = chunk.get("video_id", "")
        video_meta = metadata.get(video_id)
        video_name = video_meta.title if video_meta else video_id

        raw_text = chunk.get("text", "")
        snippet = raw_text.strip() if raw_text else ""

        citation = Citation(
            video_name=video_name,
            chunk_id=chunk_id,
            timestamp=chunk.get("timestamp", ""),
            text_snippet=snippet,
        )
        citations.append(citation)

    logger.info(f"Built {len(citations)} citations")
    return citations


def format_citations_for_prompt(citations: list[Citation]) -> str:
    """Format citations as text to include in the LLM prompt."""
    if not citations:
        return ""

    lines = ["\n--- Sources ---"]
    for i, c in enumerate(citations, 1):
        lines.append(
            f"[{i}] {c.video_name} | {c.chunk_id} | {c.timestamp}"
        )
    return "\n".join(lines)


def format_citations_for_response(citations: list[Citation]) -> str:
    """Format citations for appending to the sync endpoint response.

    Issue 6 fix: removed markdown bold/asterisks — plain text only so
    the response does not contain literal ** characters when rendered.
    """
    if not citations:
        return ""

    lines = ["\n\nSources:"]
    for i, c in enumerate(citations, 1):
        lines.append(
            f"{i}. {c.video_name} - {c.timestamp} (Chunk: {c.chunk_id})"
        )
        if c.text_snippet:
            lines.append(f"   {c.text_snippet}")
    return "\n".join(lines)
