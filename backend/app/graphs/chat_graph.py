"""
LangGraph Chat Pipeline.

Flow:
  START → route_intent → retrieve_metadata → conditional_retrieval
  → rerank → analyze → build_citations → update_memory
  → build_prompt (for prep graph) OR generate_response (for full graph) → END
"""

from typing import TypedDict
import asyncio
import time
# pyrefly: ignore [missing-import]
from langgraph.graph import StateGraph, END

from app.models.chat import IntentType, AnalysisResult
from app.services.intent_router import route_intent
from app.services.metadata_db import get_video, list_videos
from app.services.embedder import embed_single
from app.services.vector_store import search_similar
from app.services.reranker import rerank_chunks
from app.services.analysis_engine import compute_analysis
from app.services.context_builder import build_context
from app.services.citation_builder import build_citations
from app.services.memory import get_memory
from app.services.llm import generate_response as llm_generate
from app.prompts.system import SYSTEM_PROMPT
from app.prompts.engagement import ENGAGEMENT_PROMPT
from app.prompts.comparison import COMPARISON_PROMPT
from app.prompts.hook_analysis import HOOK_ANALYSIS_PROMPT
from app.prompts.creator_info import CREATOR_INFO_PROMPT
from app.monitoring.logger import get_logger
from app.monitoring.metrics import increment_counter, record_latency
from app.models.video import VideoMetadata

logger = get_logger(__name__)


class ChatPipelineState(TypedDict):
    """State passed through the chat graph."""
    query: str
    session_id: str
    video_ids: list[str]
    intent: str
    intent_confidence: float
    metadata: dict  # video_id -> dict
    retrieved_chunks: list[dict]
    reranked_chunks: list[dict]
    analysis: dict | None
    citations: list[dict]
    memory_summary: str
    context: str
    prompt: str
    response: str
    error: str | None


# --- Graph Nodes ---


async def route_intent_node(state: ChatPipelineState) -> dict:
    """Extract user intent."""
    start = time.perf_counter()
    intent, conf = await route_intent(state["query"])
    latency_ms = (time.perf_counter() - start) * 1000
    record_latency("route_intent_ms", latency_ms)
    logger.info(f"Intent routed: {intent} (conf: {conf:.2f})")
    return {"intent": intent.value, "intent_confidence": conf}


async def retrieve_metadata_node(state: ChatPipelineState) -> dict:
    """Retrieve SQL metadata."""
    vids = state.get("video_ids", [])
    meta_dict = {}
    
    if vids:
        # Fetch specific videos
        for v in vids:
            row = await get_video(v)
            if row:
                meta_dict[row.video_id] = row.model_dump()
    else:
        # Fallback to recent videos
        recent = await list_videos(limit=5)
        for r in recent:
            meta_dict[r.video_id] = r.model_dump()

    if not meta_dict:
        return {"error": "No videos found in database."}

    logger.info(f"Retrieved metadata for {len(meta_dict)} videos")
    return {"metadata": meta_dict}


async def conditional_retrieval_node(state: ChatPipelineState) -> dict:
    """Retrieve chunks via Qdrant only if intent requires it."""
    intent = state.get("intent")
    
    if intent in [IntentType.ENGAGEMENT.value, IntentType.CREATOR_INFO.value]:
        logger.info(f"Skipping vector search for intent: {intent}")
        return {"retrieved_chunks": []}

    try:
        query_embedding = await asyncio.to_thread(embed_single, state["query"])
        video_ids = list(state.get("metadata", {}).keys())

        chunks = await asyncio.to_thread(
            search_similar,
            query_embedding=query_embedding,
            video_ids=video_ids if video_ids else None,
            top_k=20,
        )

        logger.info(f"Retrieved {len(chunks)} chunks from Qdrant")
        return {"retrieved_chunks": chunks}
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        return {"retrieved_chunks": []}


async def rerank_node(state: ChatPipelineState) -> dict:
    """Rerank retrieved chunks using CrossEncoder."""
    chunks = state.get("retrieved_chunks", [])
    if not chunks:
        return {"reranked_chunks": []}

    try:
        reranked = await asyncio.to_thread(rerank_chunks, state["query"], chunks, 5)
        return {"reranked_chunks": reranked}
    except Exception as e:
        logger.error(f"Reranking failed: {e}")
        return {"reranked_chunks": chunks[:5]}


async def analyze_node(state: ChatPipelineState) -> dict:
    """Run deeper comparative analysis if needed."""
    video_ids = list(state.get("metadata", {}).keys())
    if len(video_ids) < 2:
        return {"analysis": None}

    meta_dict = state["metadata"]
    videos = [VideoMetadata(**meta_dict[vid]) for vid in video_ids]
    
    try:
        # We pass empty dict for transcripts for now, 
        # meaning question/cta counts will be 0 unless we fetch transcripts here.
        analysis = await asyncio.to_thread(
            compute_analysis, videos, {}
        )
        return {"analysis": analysis.model_dump()}
    except Exception as e:
        logger.error(f"Analysis node failed: {e}")
        return {"analysis": None}


async def build_citations_node(state: ChatPipelineState) -> dict:
    """Generate citations from reranked chunks."""
    chunks = state.get("reranked_chunks", [])
    metadata_dict = state.get("metadata", {})
    meta_objects = {vid: VideoMetadata(**m) for vid, m in metadata_dict.items()}
    citations = build_citations(chunks, meta_objects)
    return {"citations": [c.model_dump() for c in citations]}


async def update_memory_node(state: ChatPipelineState) -> dict:
    """Retrieve memory context."""
    session_id = state.get("session_id", "default")
    memory = await get_memory(session_id)
    return {"memory_summary": memory}


async def build_prompt_node(state: ChatPipelineState) -> dict:
    """Build the LLM prompt without calling it. Used for SSE."""
    intent = state.get("intent", "general_comparison")
    metadata = state.get("metadata", {})
    chunks = state.get("reranked_chunks", [])

    meta_objects = {vid: VideoMetadata(**m) for vid, m in metadata.items()}

    analysis_obj = None
    if state.get("analysis"):
        analysis_obj = AnalysisResult(**state["analysis"])

    context = build_context(
        IntentType(intent), meta_objects, chunks, analysis_obj
    )

    memory_text = (
        f"\nConversation Context:\n{state.get('memory_summary', '')}"
        if state.get("memory_summary") else ""
    )

    prompt_map = {
        IntentType.ENGAGEMENT.value: ENGAGEMENT_PROMPT,
        IntentType.CREATOR_INFO.value: CREATOR_INFO_PROMPT,
        IntentType.HOOK_COMPARISON.value: HOOK_ANALYSIS_PROMPT,
        IntentType.GENERAL_COMPARISON.value: COMPARISON_PROMPT,
    }

    template = prompt_map.get(intent, COMPARISON_PROMPT)
    prompt = template.format(
        system=SYSTEM_PROMPT,
        context=context,
        memory=memory_text,
        query=state["query"],
    )

    return {"prompt": prompt, "context": context}


async def generate_response_node(state: ChatPipelineState) -> dict:
    """Sync LLM response generation."""
    prompt_res = await build_prompt_node(state)
    prompt = prompt_res["prompt"]
    
    start = time.perf_counter()
    try:
        response = await llm_generate(prompt)
        latency_ms = (time.perf_counter() - start) * 1000
        record_latency("llm_latency_ms", latency_ms)
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        response = "I encountered an error generating the response. Please try again."

    return {"response": response, "context": prompt_res["context"]}


# --- Graph Construction ---

def build_chat_graph() -> StateGraph:
    workflow = StateGraph(ChatPipelineState)
    workflow.add_node("route_intent", route_intent_node)
    workflow.add_node("retrieve_metadata", retrieve_metadata_node)
    workflow.add_node("conditional_retrieval", conditional_retrieval_node)
    workflow.add_node("rerank", rerank_node)
    workflow.add_node("analyze", analyze_node)
    workflow.add_node("build_citations", build_citations_node)
    workflow.add_node("update_memory", update_memory_node)
    workflow.add_node("generate_response", generate_response_node)

    workflow.set_entry_point("route_intent")
    workflow.add_edge("route_intent", "retrieve_metadata")
    workflow.add_edge("retrieve_metadata", "conditional_retrieval")
    workflow.add_edge("conditional_retrieval", "rerank")
    workflow.add_edge("rerank", "analyze")
    workflow.add_edge("analyze", "build_citations")
    workflow.add_edge("build_citations", "update_memory")
    workflow.add_edge("update_memory", "generate_response")
    workflow.add_edge("generate_response", END)

    return workflow.compile()


def build_chat_prep_graph() -> StateGraph:
    workflow = StateGraph(ChatPipelineState)
    workflow.add_node("route_intent", route_intent_node)
    workflow.add_node("retrieve_metadata", retrieve_metadata_node)
    workflow.add_node("conditional_retrieval", conditional_retrieval_node)
    workflow.add_node("rerank", rerank_node)
    workflow.add_node("analyze", analyze_node)
    workflow.add_node("build_citations", build_citations_node)
    workflow.add_node("update_memory", update_memory_node)
    workflow.add_node("build_prompt", build_prompt_node)

    workflow.set_entry_point("route_intent")
    workflow.add_edge("route_intent", "retrieve_metadata")
    workflow.add_edge("retrieve_metadata", "conditional_retrieval")
    workflow.add_edge("conditional_retrieval", "rerank")
    workflow.add_edge("rerank", "analyze")
    workflow.add_edge("analyze", "build_citations")
    workflow.add_edge("build_citations", "update_memory")
    workflow.add_edge("update_memory", "build_prompt")
    workflow.add_edge("build_prompt", END)

    return workflow.compile()


chat_app = build_chat_graph()
chat_prep_app = build_chat_prep_graph()


async def run_chat(query: str, session_id: str = "default", video_ids: list[str] = None) -> dict:
    increment_counter("langgraph_chat_invocations")
    initial_state = {"query": query, "session_id": session_id, "video_ids": video_ids or []}
    start = time.perf_counter()
    try:
        result = await chat_app.ainvoke(initial_state)
        # Issue 5 fix: track_latency is a decorator factory, not a direct call.
        # Use record_latency() which is the correct direct measurement function.
        record_latency("chat_pipeline_ms", (time.perf_counter() - start) * 1000)
        return result
    except Exception as e:
        logger.error(f"Chat graph failed: {e}", exc_info=True)
        return {"error": str(e)}


async def run_chat_prep(query: str, session_id: str = "default", video_ids: list[str] = None) -> dict:
    increment_counter("langgraph_chat_prep_invocations")
    initial_state = {"query": query, "session_id": session_id, "video_ids": video_ids or []}
    try:
        return await chat_prep_app.ainvoke(initial_state)
    except Exception as e:
        logger.error(f"Chat prep graph failed: {e}", exc_info=True)
        return {"error": str(e)}