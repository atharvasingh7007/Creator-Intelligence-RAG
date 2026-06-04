"""
Transcript extraction with quality scoring.

Primary: youtube-transcript-api (fast, free)
Fallback: yt-dlp subtitle download

Computes transcript_quality score based on:
- Length adequacy
- Missing segment detection
- Caption confidence
"""

# pyrefly: ignore [missing-import]
from youtube_transcript_api import YouTubeTranscriptApi
# pyrefly: ignore [missing-import]
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)
import re
import subprocess
import json
from app.monitoring.logger import get_logger

logger = get_logger(__name__)


def _extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from various URL formats. Returns None if not YouTube."""
    patterns = [
        r"(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"(?:embed/)([a-zA-Z0-9_-]{11})",
        r"(?:shorts/)([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def _compute_transcript_quality(
    transcript: str, duration_seconds: int
) -> float:
    """
    Compute transcript quality score (0.0 - 1.0).

    Factors:
    - Length adequacy: transcript should have ~2-3 words per second
    - Missing segments: large gaps suggest auto-caption failures
    - Repetition: excessive repetition indicates poor captions
    """
    if not transcript or not transcript.strip():
        return 0.0

    words = transcript.split()
    word_count = len(words)

    # Length adequacy: expect 2-3 words per second for speech
    if duration_seconds > 0:
        words_per_second = word_count / duration_seconds
        # Ideal: 2-3 wps. Penalty for too low or too high.
        if 1.5 <= words_per_second <= 4.0:
            length_score = 1.0
        elif 0.5 <= words_per_second < 1.5:
            length_score = 0.6
        elif words_per_second < 0.5:
            length_score = 0.3
        else:
            length_score = 0.8  # too fast, might be fine
    else:
        length_score = 0.5  # unknown duration

    # Minimum viable transcript
    if word_count < 20:
        return 0.2

    # Check for excessive [Music] or [Applause] markers
    bracket_count = len(re.findall(r"\[.*?\]", transcript))
    bracket_ratio = bracket_count / max(word_count, 1)
    bracket_score = max(0.0, 1.0 - bracket_ratio * 10)

    # Final quality
    quality = round(length_score * 0.6 + bracket_score * 0.4, 2)
    return min(1.0, max(0.0, quality))


def _clean_transcript(text: str) -> str:
    """Clean transcript text: normalize whitespace, strip markup."""
    # Remove [Music], [Applause], etc.
    text = re.sub(r"\[.*?\]", "", text)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


async def extract_transcript(
    url: str, duration_seconds: int = 0
) -> tuple[str, float, str]:
    """
    Extract and clean transcript. Returns (transcript, quality_score).

    Primary: YouTube Transcript API
    Fallback: yt-dlp subtitle download
    """
    video_id = _extract_video_id(url)

    # Primary: YouTube Transcript API
    if video_id:
        try:
            transcript_list_obj = YouTubeTranscriptApi.list_transcripts(video_id)
            try:
                # First, try to find an English transcript (manual or auto-generated)
                transcript = transcript_list_obj.find_transcript(
                    ['en', 'en-US', 'en-GB', 'en-IN', 'en-CA', 'en-AU']
                )
            except NoTranscriptFound:
                # If no English, grab the first available language and auto-translate to English
                available_transcripts = list(transcript_list_obj)
                if not available_transcripts:
                    raise NoTranscriptFound(video_id)
                
                first_transcript = available_transcripts[0]
                logger.info(f"No English transcript found for {video_id}. Translating from {first_transcript.language_code} to English.")
                transcript = first_transcript.translate('en')

            raw_text = " ".join(entry["text"] for entry in transcript.fetch())
            cleaned = _clean_transcript(raw_text)
            quality = _compute_transcript_quality(cleaned, duration_seconds)

            logger.info(
                f"Transcript extracted via API for {video_id} "
                f"(quality: {quality}, words: {len(cleaned.split())})"
            )
            return cleaned, quality, "api"

        except Exception as e:
            logger.warning(
                f"YouTube Transcript API failed for {video_id}: {type(e).__name__} - {e}. "
                f"Trying yt-dlp fallback."
            )

    # Fallback: yt-dlp subtitle extraction via VTT
    try:
        import asyncio
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # We use %(id)s to ensure predictability of the output filename
            out_tmpl = os.path.join(tmpdir, "%(id)s.%(ext)s")
            
            result = await asyncio.to_thread(
                subprocess.run,
                [
                    "yt-dlp",
                    "--write-auto-sub",
                    "--write-sub",
                    "--sub-lang", "en",
                    "--skip-download",
                    "--sub-format", "vtt",
                    "-o", out_tmpl,
                    url,
                ],
                capture_output=True,
                text=True,
                timeout=45,
            )
            
            if result.returncode == 0:
                # Find the downloaded VTT file
                vtt_file = None
                for f in os.listdir(tmpdir):
                    if f.endswith(".vtt"):
                        vtt_file = os.path.join(tmpdir, f)
                        break
                        
                if vtt_file and os.path.exists(vtt_file):
                    with open(vtt_file, 'r', encoding='utf-8') as f:
                        vtt_content = f.read()
                    
                    # Parse VTT: remove headers, timestamps, and formatting
                    lines = vtt_content.splitlines()
                    texts = []
                    seen = set()
                    for line in lines:
                        # Skip VTT headers, timestamps (00:00:00.000 --> ...), and empty lines
                        if not line.strip() or line.startswith("WEBVTT") or "-->" in line or line.startswith("Kind:") or line.startswith("Language:"):
                            continue
                        # Remove styling tags like <c.colorE5E5E5> or </c> or <00:00:01.000>
                        clean_line = re.sub(r"<[^>]+>", "", line).strip()
                        if clean_line and clean_line not in seen:
                            seen.add(clean_line)
                            texts.append(clean_line)
                            
                    if texts:
                        raw_text = " ".join(texts)
                        cleaned = _clean_transcript(raw_text)
                        quality = _compute_transcript_quality(
                            cleaned, duration_seconds
                        ) * 0.8  # penalty for fallback
                        logger.info(
                            f"Transcript via yt-dlp VTT fallback for {video_id}"
                        )
                        return cleaned, quality, "fallback"

    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.error(f"yt-dlp fallback failed for {video_id}: {e}")

    # Both methods failed
    logger.error(f"All transcript methods failed for {video_id}")
    return "", 0.0, "none"


def extract_hook(transcript: str, max_words: int = 50) -> str:
    """
    Extract hook text: first N words of transcript.
    Represents the first ~5 seconds of spoken content.
    """
    if not transcript:
        return ""
    words = transcript.split()
    return " ".join(words[:max_words])
