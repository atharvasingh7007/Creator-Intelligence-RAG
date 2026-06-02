"""
Token-based transcript chunking.

Chunk size: 400 tokens
Overlap: 50 tokens

Uses tiktoken for consistent tokenization.
"""

import tiktoken
from app.models.video import VideoChunk
from app.config import get_settings

# Use cl100k_base encoding (GPT-4 / general purpose)
_encoder = tiktoken.get_encoding("cl100k_base")


def chunk_transcript(
    transcript: str,
    video_id: str,
    duration_seconds: int = 0,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[VideoChunk]:
    """
    Split transcript into overlapping token-based chunks.

    Args:
        transcript: Full transcript text
        video_id: Video identifier for chunk IDs
        duration_seconds: Video duration for timestamp estimation
        chunk_size: Tokens per chunk (default from config: 400)
        chunk_overlap: Overlap tokens (default from config: 50)

    Returns:
        List of VideoChunk with estimated timestamps
    """
    settings = get_settings()
    chunk_size = chunk_size or settings.chunk_size
    chunk_overlap = chunk_overlap or settings.chunk_overlap

    if not transcript or not transcript.strip():
        return []

    tokens = _encoder.encode(transcript)
    total_tokens = len(tokens)

    if 0 == total_tokens:
        return []

    chunks: list[VideoChunk] = []
    start = 0
    chunk_index = 0

    while start < total_tokens:
        end = min(start + chunk_size, total_tokens)
        chunk_tokens = tokens[start:end]
        chunk_text = _encoder.decode(chunk_tokens)

        # Estimate timestamp based on position in transcript
        if duration_seconds > 0:
            position_ratio = start / total_tokens
            estimated_seconds = int(position_ratio * duration_seconds)
            hours = estimated_seconds // 3600
            minutes = (estimated_seconds % 3600) // 60
            secs = estimated_seconds % 60
            timestamp = f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            timestamp = ""

        chunk = VideoChunk(
            chunk_id=f"{video_id}_{chunk_index}",
            video_id=video_id,
            text=chunk_text.strip(),
            timestamp=timestamp,
            chunk_index=chunk_index,
        )
        chunks.append(chunk)

        # Advance by (chunk_size - overlap) for the next chunk
        start += chunk_size - chunk_overlap
        chunk_index += 1

        # Safety: if we're near the end and would create a tiny last chunk
        if start < total_tokens and (total_tokens - start) < chunk_overlap:
            # Include remaining tokens in the last chunk
            remaining_tokens = tokens[start:]
            remaining_text = _encoder.decode(remaining_tokens)
            # Append to last chunk instead of creating a tiny new one
            chunks[-1] = VideoChunk(
                chunk_id=chunks[-1].chunk_id,
                video_id=video_id,
                text=(chunks[-1].text + " " + remaining_text).strip(),
                timestamp=chunks[-1].timestamp,
                chunk_index=chunks[-1].chunk_index,
            )
            break

    return chunks
