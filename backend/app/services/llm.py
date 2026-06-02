"""
Gemini Flash LLM service.

Handles: summary generation, intent classification (fallback),
and streaming response generation.
"""

import asyncio
# pyrefly: ignore [missing-import]
import google.generativeai as genai
from typing import AsyncGenerator
from app.config import get_settings
from app.monitoring.logger import get_logger

logger = get_logger(__name__)

_model = None


def _get_model():
    """Initialize Gemini Flash model."""
    global _model
    if _model is None:
        settings = get_settings()
        genai.configure(api_key=settings.gemini_api_key)
        _model = genai.GenerativeModel("gemini-2.5-flash")
        logger.info("Gemini Flash model initialized")
    return _model


async def generate_summary(transcript: str) -> str:
    """Generate a concise summary of a video transcript."""
    if not transcript:
        return ""

    model = _get_model()
    prompt = (
        "Summarize this video transcript in 3-5 sentences. "
        "Focus on key themes, main topics, and unique insights.\n\n"
        f"Transcript:\n{transcript[:3000]}"  # Cap to avoid token overflow
    )

    for attempt in range(3):
        try:
            response = await model.generate_content_async(prompt)
            text = getattr(response, 'text', None)
            return (text or "").strip()
        except Exception as e:
            if "429" in str(e) or "Quota exceeded" in str(e):
                logger.warning(f"Rate limit hit in summary. Retrying in 15s ({attempt+1}/3)...")
                await asyncio.sleep(15)
                continue
            logger.error(f"Summary generation failed: {e}")
            return ""
    return ""


async def classify_intent(query: str) -> tuple[str, float]:
    """
    LLM-based intent classification (fallback for hybrid router).

    Returns (intent_name, confidence).
    """
    model = _get_model()
    prompt = (
        "Classify this user query into exactly one intent. "
        "Respond with ONLY the intent name, nothing else.\n\n"
        "Intents:\n"
        "- engagement: about views, likes, engagement rate, performance\n"
        "- creator_info: about who the creator is, channel info\n"
        "- hook_comparison: about comparing video intros/hooks/openings\n"
        "- general_comparison: comparing videos, why one outperformed\n\n"
        f"Query: {query}\n\n"
        "Intent:"
    )

    for attempt in range(3):
        try:
            response = await model.generate_content_async(prompt)
            text = getattr(response, 'text', None)
            intent = (text or "").strip().lower()
            # Validate
            valid = ["engagement", "creator_info", "hook_comparison", "general_comparison"]
            if intent in valid:
                return intent, 0.85
            return "general_comparison", 0.5
        except Exception as e:
            if "429" in str(e) or "Quota exceeded" in str(e):
                logger.warning(f"Rate limit hit in intent. Retrying in 15s ({attempt+1}/3)...")
                await asyncio.sleep(15)
                continue
            logger.error(f"Intent classification failed: {e}")
            return "general_comparison", 0.3
    return "general_comparison", 0.3


async def stream_response(
    prompt: str,
) -> AsyncGenerator[str, None]:
    """
    Stream LLM response token-by-token.
    Yields text chunks for SSE streaming.
    """
    model = _get_model()

    for attempt in range(3):
        try:
            response = await model.generate_content_async(prompt, stream=True)
            async for chunk in response:
                chunk_text = getattr(chunk, 'text', None)
                if chunk_text:
                    yield chunk_text
            return
        except Exception as e:
            if "429" in str(e) or "Quota exceeded" in str(e):
                if attempt < 2:
                    yield f"\n\n[Rate limit hit. Pausing for 15s before retry (Attempt {attempt+1}/3)...]\n\n"
                    await asyncio.sleep(15)
                    continue
                else:
                    yield "\n\n[Error: Gemini rate limit completely exhausted. Please wait a minute and try again.]"
                    return
            logger.error(f"Streaming generation failed: {e}")
            yield f"\n\n[Error: Generation failed - {str(e)}]"
            return


async def generate_response(prompt: str) -> str:
    """Non-streaming generation for simple responses."""
    model = _get_model()
    for attempt in range(3):
        try:
            response = await model.generate_content_async(prompt)
            text = getattr(response, 'text', None)
            return (text or "").strip()
        except Exception as e:
            if "429" in str(e) or "Quota exceeded" in str(e):
                logger.warning(f"Rate limit hit in generate. Retrying in 15s ({attempt+1}/3)...")
                await asyncio.sleep(15)
                continue
            logger.error(f"Generation failed: {e}")
            return f"Error generating response: {str(e)}"
    return "Error: Gemini rate limit exceeded. Please wait and try again."
