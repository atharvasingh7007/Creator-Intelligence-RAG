"""
Hybrid intent router.

Layer 1: Keyword-based matching (instant, free)
Layer 2: LLM classification fallback (only if confidence < threshold)

Looks senior. Avoids unnecessary LLM latency for obvious queries.
"""

import re
from app.models.chat import IntentType
from app.services.llm import classify_intent as llm_classify
from app.monitoring.logger import get_logger

logger = get_logger(__name__)

# Keyword patterns for each intent
INTENT_PATTERNS: dict[IntentType, list[str]] = {
    IntentType.ENGAGEMENT: [
        r"\bengagement\b",
        r"\bviews?\b",
        r"\blikes?\b",
        r"\bperform",
        r"\bmetrics?\b",
        r"\brate\b",
        r"\bstats?\b",
        r"\bstatistics\b",
        r"\banalytics\b",
        r"\bhow\s+many\b",
        r"\bcount\b",
        r"\bnumbers?\b",
    ],
    IntentType.CREATOR_INFO: [
        r"\bwho\s+(is|are)\b",
        r"\bcreator\b",
        r"\bchannel\b",
        r"\babout\b",
        r"\buploader\b",
        r"\bfollowers?\b",
        r"\bstrategy\b",
        r"\bapproach\b",
        r"\bstyle\b",
        r"\bbackground\b",
        r"\bwhat\s+does\s+this\s+creator\b",
        r"\bpersonality\b",
        r"\bniche\b",
    ],
    IntentType.HOOK_COMPARISON: [
        r"\bhooks?\b",
        r"\bintro\b",
        r"\bopening\b",
        r"\bopen\b.*\bvideos?\b",
        r"\bfirst\s+(few\s+)?seconds?\b",
        r"\battention\b",
        r"\bstart\b",
        r"\bbeginning\b",
    ],
    IntentType.GENERAL_COMPARISON: [
        r"\bcompare\b",
        r"\bbetter\b",
        r"\boutperform",
        r"\bwhy\b.*\b(did|does|more|get|got)\b",
        r"\bdifference\b",
        r"\bvs\.?\b",
        r"\bversus\b",
        r"\bwhat\s+(is|was)\s+this\s+video\s+about\b",
        r"\bwhat\s+is\s+this\s+about\b",
        r"\btell\s+me\s+about\b",
        r"\bexplain\b",
        r"\bsummar",
        r"\boverview\b",
        r"\bwhat\s+topics?\b",
        r"\bwhat\s+does\s+it\s+cover\b",
    ],
}

CONFIDENCE_THRESHOLD = 0.3


def _keyword_score(query: str, patterns: list[str]) -> float:
    """Score a query against keyword patterns."""
    query_lower = query.lower()
    matches = sum(
        1 for pattern in patterns if re.search(pattern, query_lower)
    )
    if not patterns:
        return 0.0
    # Use raw match count not ratio — short pattern lists penalize intents unfairly
    return float(matches)


async def route_intent(query: str) -> tuple[IntentType, float]:
    """
    Hybrid intent routing.

    1. Score all intents by keyword match
    2. If top score > threshold → return immediately (no LLM call)
    3. If ambiguous → fall back to Gemini Flash classification
    """
    scores: dict[IntentType, float] = {}
    for intent, patterns in INTENT_PATTERNS.items():
        scores[intent] = _keyword_score(query, patterns)

    # Get best keyword match
    best_intent = max(scores, key=scores.get)
    best_score = scores[best_intent]

    # Clear winner: top score > threshold
    if best_score >= CONFIDENCE_THRESHOLD:
        logger.info(
            f"Intent routed via keywords: {best_intent.value} "
            f"(score: {best_score:.2f})"
        )
        return best_intent, best_score

    # All scores zero or ambiguous — fall back to LLM
    logger.info(
        f"Keyword routing ambiguous (best: {best_score:.2f}). "
        f"Falling back to LLM classification."
    )
    intent_str, confidence = await llm_classify(query)

    try:
        intent = IntentType(intent_str)
    except ValueError:
        intent = IntentType.GENERAL_COMPARISON
        confidence = 0.4

    logger.info(
        f"Intent routed via LLM: {intent.value} (confidence: {confidence:.2f})"
    )
    return intent, confidence
