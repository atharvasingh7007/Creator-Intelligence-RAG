"""
Video metadata extraction via yt-dlp.
Supports YouTube and Instagram.
Computes engagement rate: (likes + comments) / views * 100
"""

import hashlib
import json
import re
import subprocess
from app.models.video import VideoMetadata
from app.monitoring.logger import get_logger

logger = get_logger(__name__)

# --- URL patterns ---

_YOUTUBE_PATTERNS = [
    r"(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})",
    r"(?:embed/)([a-zA-Z0-9_-]{11})",
    r"(?:shorts/)([a-zA-Z0-9_-]{11})",
]

_INSTAGRAM_PATTERNS = [
    r"instagram\.com/(?:p|reel|tv)/([a-zA-Z0-9_-]+)",
]


def detect_platform(url: str) -> str:
    """Detect platform from URL hostname."""
    url_lower = url.lower()
    if any(host in url_lower for host in ("youtube.com", "youtu.be", "youtube-nocookie.com")):
        return "youtube"
    if "instagram.com" in url_lower:
        return "instagram"
    return "unknown"


def compute_video_hash(url: str) -> str:
    """SHA256 fingerprint of the canonical video/post ID for deduplication."""
    canonical = url.strip()
    platform = detect_platform(canonical)

    patterns = []
    if "youtube" == platform:
        patterns = _YOUTUBE_PATTERNS
    elif "instagram" == platform:
        patterns = _INSTAGRAM_PATTERNS

    for pattern in patterns:
        match = re.search(pattern, canonical)
        if match:
            canonical = match.group(1)
            break

    return hashlib.sha256(canonical.encode()).hexdigest()


def compute_engagement_rate(likes: int, comments: int, views: int) -> float:
    """Engagement Rate = (likes + comments) / views * 100"""
    if 0 == views:
        return 0.0
    return round((likes + comments) / views * 100, 4)


async def extract_metadata(url: str) -> VideoMetadata:
    """Extract metadata using yt-dlp."""
    platform = detect_platform(url)
    timeout = 30 if platform == "youtube" else 45
    
    import asyncio
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            [
                "yt-dlp",
                "--dump-json",
                "--no-playlist",
                url,
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout,
        )
        info = json.loads(result.stdout)
        
        # Safe extraction with defaults
        views = info.get("view_count", 0) or 0
        likes = info.get("like_count", 0) or 0
        comments = info.get("comment_count", 0) or 0
        
        # Fix for Instagram float duration
        raw_duration = info.get("duration", 0) or 0
        duration = int(float(raw_duration))
        
        metadata = VideoMetadata(
            video_id=info.get("id", ""),
            video_hash=compute_video_hash(url),
            url=url,
            title=info.get("title", ""),
            creator_name=info.get("uploader", ""),
            views=views,
            likes=likes,
            comments=comments,
            follower_count=info.get("channel_follower_count", 0) or 0,
            upload_date=info.get("upload_date", ""),
            hashtags=info.get("tags", []),
            duration=duration,
            engagement_rate=compute_engagement_rate(likes, comments, views),
            platform=platform,
        )
        logger.info(f"Extracted metadata for {metadata.video_id} ({platform})")
        return metadata

    except subprocess.CalledProcessError as e:
        logger.error(f"yt-dlp failed: {e.stderr}")
        raise ValueError(f"Failed to extract metadata: {e.stderr}")
    except json.JSONDecodeError:
        logger.error("Failed to parse yt-dlp output")
        raise ValueError("Invalid metadata format from yt-dlp")
    except subprocess.TimeoutExpired:
        logger.error(f"yt-dlp timeout after {timeout}s for {url}")
        raise ValueError(f"Metadata extraction timed out")