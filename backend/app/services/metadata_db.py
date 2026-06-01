"""
PostgreSQL metadata storage via SQLAlchemy async.

Stores video metadata for fast structured retrieval.
Handles fingerprint dedup checks.
"""

# pyrefly: ignore [missing-import]
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
# pyrefly: ignore [missing-import]
from sqlalchemy import String, Integer, Float, Text, JSON, select, desc
# pyrefly: ignore [missing-import]
from sqlalchemy.dialects.postgresql import insert
from datetime import datetime, timedelta, timezone
from app.config import get_settings
from app.models.video import VideoMetadata
from app.monitoring.logger import get_logger

logger = get_logger(__name__)

_engine = None
_session_factory = None


class Base(DeclarativeBase):
    pass


class VideoRecord(Base):
    """SQLAlchemy model for video metadata."""

    __tablename__ = "videos"

    video_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    video_hash: Mapped[str] = mapped_column(String(64), index=True)
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    creator_name: Mapped[str] = mapped_column(String(256))
    views: Mapped[int] = mapped_column(Integer, default=0)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    follower_count: Mapped[int] = mapped_column(Integer, default=0)
    upload_date: Mapped[str] = mapped_column(String(32), default="")
    hashtags: Mapped[dict] = mapped_column(JSON, default=list)
    duration: Mapped[int] = mapped_column(Integer, default=0)
    engagement_rate: Mapped[float] = mapped_column(Float, default=0.0)
    hook_text: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    platform: Mapped[str] = mapped_column(String(32), default="youtube")
    transcript_quality: Mapped[float] = mapped_column(Float, default=1.0)
    ingested_at: Mapped[str] = mapped_column(String(64), default="")
    metadata_refreshed_at: Mapped[str] = mapped_column(String(64), default="")


class SessionMemory(Base):
    """SQLAlchemy model for conversation memory summaries."""

    __tablename__ = "session_memory"

    session_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[str] = mapped_column(String(64), default="")


async def init_db():
    """Initialize database engine and create tables."""
    global _engine, _session_factory
    settings = get_settings()

    _engine = create_async_engine(settings.postgres_url, echo=False)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database initialized")


async def get_session() -> AsyncSession:
    """Get a database session."""
    if _session_factory is None:
        await init_db()
    return _session_factory()


async def check_fingerprint(video_hash: str) -> bool:
    """Check if a video with this hash already exists."""
    session = await get_session()
    async with session:
        result = await session.execute(
            select(VideoRecord).where(VideoRecord.video_hash == video_hash)
        )
        return result.scalar_one_or_none() is not None


REFRESH_TTL_HOURS = 24


async def check_fingerprint_with_ttl(video_hash: str) -> tuple[bool, bool]:
    """Check if video exists and whether its metadata is stale.

    Returns:
        (exists, needs_refresh): exists=True if video is in DB,
        needs_refresh=True if metadata is older than REFRESH_TTL_HOURS.
    """
    session = await get_session()
    async with session:
        result = await session.execute(
            select(VideoRecord).where(VideoRecord.video_hash == video_hash)
        )
        record = result.scalar_one_or_none()
        if record is None:
            return False, False

        refreshed_at = record.metadata_refreshed_at or record.ingested_at
        if not refreshed_at:
            return True, True

        try:
            last_refresh = datetime.fromisoformat(refreshed_at)
            if last_refresh.tzinfo is None:
                last_refresh = last_refresh.replace(tzinfo=timezone.utc)
            age = datetime.now(timezone.utc) - last_refresh
            needs_refresh = False
        except (ValueError, TypeError):
            needs_refresh = True

        return True, needs_refresh


async def get_video_by_hash(video_hash: str) -> VideoMetadata | None:
    """Retrieve video metadata by hash."""
    session = await get_session()
    async with session:
        result = await session.execute(
            select(VideoRecord).where(VideoRecord.video_hash == video_hash)
        )
        record = result.scalar_one_or_none()
        if record is None:
            return None
        return _record_to_metadata(record)


async def save_video(metadata: VideoMetadata):
    """Save video metadata to PostgreSQL with upsert."""
    session = await get_session()
    async with session:
        stmt = insert(VideoRecord).values(
            video_id=metadata.video_id,
            video_hash=metadata.video_hash,
            url=metadata.url,
            title=metadata.title,
            creator_name=metadata.creator_name,
            views=metadata.views,
            likes=metadata.likes,
            comments=metadata.comments,
            follower_count=metadata.follower_count,
            upload_date=metadata.upload_date,
            hashtags=metadata.hashtags,
            duration=metadata.duration,
            engagement_rate=metadata.engagement_rate,
            hook_text=metadata.hook_text,
            summary=metadata.summary,
            platform=metadata.platform,
            transcript_quality=metadata.transcript_quality,
            ingested_at=metadata.ingested_at,
            metadata_refreshed_at=datetime.now(timezone.utc).isoformat(),
        )

        stmt = stmt.on_conflict_do_update(
            index_elements=["video_id"],
            set_={
                "video_hash": stmt.excluded.video_hash,
                "url": stmt.excluded.url,
                "title": stmt.excluded.title,
                "creator_name": stmt.excluded.creator_name,
                "views": stmt.excluded.views,
                "likes": stmt.excluded.likes,
                "comments": stmt.excluded.comments,
                "follower_count": stmt.excluded.follower_count,
                "upload_date": stmt.excluded.upload_date,
                "hashtags": stmt.excluded.hashtags,
                "duration": stmt.excluded.duration,
                "engagement_rate": stmt.excluded.engagement_rate,
                "hook_text": stmt.excluded.hook_text,
                "summary": stmt.excluded.summary,
                "platform": stmt.excluded.platform,
                "transcript_quality": stmt.excluded.transcript_quality,
                "ingested_at": stmt.excluded.ingested_at,
                "metadata_refreshed_at": stmt.excluded.metadata_refreshed_at,
            },
        )

        await session.execute(stmt)
        await session.commit()
        logger.info(f"Saved metadata for video: {metadata.video_id}")


async def get_video(video_id: str) -> VideoMetadata | None:
    """Retrieve video metadata by ID."""
    session = await get_session()
    async with session:
        result = await session.execute(
            select(VideoRecord).where(VideoRecord.video_id == video_id)
        )
        record = result.scalar_one_or_none()
        if record is None:
            return None
        return _record_to_metadata(record)


async def list_videos(limit: int = 100) -> list[VideoMetadata]:
    """List ingested videos ordered by most recently ingested first."""
    session = await get_session()
    async with session:
        # Issue 2 fix: ORDER BY ingested_at DESC so sidebar order is
        # deterministic and most recently added video appears first.
        result = await session.execute(
            select(VideoRecord)
            .order_by(desc(VideoRecord.ingested_at))
            .limit(limit)
        )
        records = result.scalars().all()
        return [_record_to_metadata(r) for r in records]


def _record_to_metadata(record: VideoRecord) -> VideoMetadata:
    """Convert SQLAlchemy record to Pydantic model."""
    return VideoMetadata(
        video_id=record.video_id,
        video_hash=record.video_hash,
        url=record.url,
        title=record.title,
        creator_name=record.creator_name,
        views=record.views,
        likes=record.likes,
        comments=record.comments,
        follower_count=record.follower_count,
        upload_date=record.upload_date,
        hashtags=record.hashtags if isinstance(record.hashtags, list) else [],
        duration=record.duration,
        engagement_rate=record.engagement_rate,
        hook_text=record.hook_text,
        summary=record.summary,
        platform=record.platform,
        transcript_quality=record.transcript_quality,
        ingested_at=record.ingested_at,
    )


async def get_session_memory(session_id: str) -> str:
    """Retrieve conversation summary for a session."""
    session = await get_session()
    async with session:
        result = await session.execute(
            select(SessionMemory).where(SessionMemory.session_id == session_id)
        )
        record = result.scalar_one_or_none()
        return record.summary if record else ""


async def update_session_memory(session_id: str, summary: str):
    """Update conversation summary for a session."""
    session = await get_session()
    async with session:
        now_str = datetime.now(timezone.utc).isoformat()
        stmt = insert(SessionMemory).values(
            session_id=session_id,
            summary=summary,
            updated_at=now_str,
        ).on_conflict_do_update(
            index_elements=["session_id"],
            set_={"summary": summary, "updated_at": now_str},
        )
        await session.execute(stmt)
        await session.commit()
