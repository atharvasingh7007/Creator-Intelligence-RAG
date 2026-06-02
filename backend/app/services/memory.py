"""
Conversation Summary Memory.

Uses summary compression instead of buffer memory.
Buffers grow infinitely. Summaries remain bounded.

Stores: prior conclusions, user preferences, previous comparisons.
"""

from app.services.llm import generate_response
from app.services.metadata_db import (
    get_session_memory, update_session_memory, get_session, SessionMemory,
)
from app.monitoring.logger import get_logger
from sqlalchemy import delete

logger = get_logger(__name__)


async def get_memory(session_id: str) -> str:
    """Retrieve conversation summary for a session from PostgreSQL."""
    return await get_session_memory(session_id)


async def update_memory(
    session_id: str,
    query: str,
    response: str,
) -> str:
    """
    Update conversation memory by compressing the latest exchange
    into the running summary.
    """
    existing = await get_session_memory(session_id)

    # Build compression prompt
    prompt = (
        "You are a conversation memory manager. "
        "Compress the following into a brief summary that captures:\n"
        "- Key conclusions reached\n"
        "- User preferences expressed\n"
        "- Video comparisons made\n"
        "- Important facts established\n\n"
        "Keep it under 200 words. Focus on facts, not conversation flow.\n\n"
    )

    if existing:
        prompt += f"Previous Summary:\n{existing}\n\n"

    prompt += f"Latest Exchange:\nUser: {query}\nAssistant: {response[:500]}\n\n"
    prompt += "Updated Summary:"

    try:
        new_summary = await generate_response(prompt)
        await update_session_memory(session_id, new_summary)
        logger.info(
            f"Memory updated for session {session_id} "
            f"({len(new_summary)} chars)"
        )
        return new_summary
    except Exception as e:
        logger.error(f"Memory update failed: {e}")
        return existing


async def clear_memory(session_id: str):
    """Clear memory for a session from PostgreSQL."""
    try:
        session = await get_session()
        async with session:
            await session.execute(
                delete(SessionMemory).where(SessionMemory.session_id == session_id)
            )
            await session.commit()
        logger.info(f"Memory cleared for session {session_id}")
    except Exception as e:
        logger.error(f"Failed to clear memory for session {session_id}: {e}")
