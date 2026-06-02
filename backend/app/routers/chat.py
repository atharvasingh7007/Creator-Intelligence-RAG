"""
Chat API router with SSE streaming.

Endpoints:
  POST /api/chat          — streaming chat via SSE (LangGraph prep + streaming LLM)
  POST /api/chat/sync     — non-streaming chat (full LangGraph pipeline)
  DELETE /api/chat/{sid}   — clear session memory
"""

import json
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, HTTPException
# pyrefly: ignore [missing-import]
from fastapi.responses import StreamingResponse
from app.models.chat import ChatRequest
from app.graphs.chat_graph import run_chat, run_chat_prep
from app.services.llm import stream_response
from app.services.memory import clear_memory, update_memory
from app.services.citation_builder import format_citations_for_response
from app.monitoring.logger import get_logger
from app.monitoring.metrics import increment_counter

logger = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


async def _build_streaming_chat(request: ChatRequest):
    """
    SSE streaming chat — powered by LangGraph.

    Runs the full LangGraph prep pipeline (intent -> metadata -> retrieval ->
    rerank -> analysis -> citations -> memory -> prompt), then streams the
    LLM response token-by-token via SSE.

    SSE event shapes are aligned with the frontend SSEEvent interface:
      { type: "intent",    intent, confidence }
      { type: "metadata",  videos }
      { type: "analysis",  analysis }
      { type: "citations", citations }
      { type: "token",     content }
      { type: "done" }
      { type: "error",     content }
    """
    # 1. Run the LangGraph prep pipeline
    try:
        state = await run_chat_prep(
            query=request.query,
            session_id=request.session_id,
            video_ids=request.video_ids,
        )
    except Exception as e:
        logger.error(f"LangGraph prep failed: {e}")
        yield f"data: {json.dumps({'type': 'error', 'content': f'Pipeline error: {str(e)}'})}\n\n"
        return

    if state.get("error") and not state.get("metadata"):
        yield f"data: {json.dumps({'type': 'error', 'content': state['error']})}\n\n"
        return

    # 2. Emit intermediate SSE events from LangGraph state.
    # Each event shape matches the typed SSEEvent interface in types.ts.

    yield f"data: {json.dumps({'type': 'intent', 'intent': state.get('intent', ''), 'confidence': state.get('intent_confidence', 0.0)})}\n\n"

    metadata_dict = state.get("metadata", {})
    if metadata_dict:
        yield f"data: {json.dumps({'type': 'metadata', 'videos': list(metadata_dict.values())})}\n\n"

    # Issue fixed: state key is "analysis" not "analysis_result".
    # Event field is "analysis" (typed dict) not "content" (string).
    analysis = state.get("analysis")
    if analysis:
        yield f"data: {json.dumps({'type': 'analysis', 'analysis': analysis})}\n\n"

    citations = state.get("citations", [])
    if citations:
        yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"

    prompt = state.get("prompt")
    if not prompt:
        yield f"data: {json.dumps({'type': 'error', 'content': 'Failed to build prompt.'})}\n\n"
        return

    # 3. Stream LLM response token by token.
    full_response = ""
    try:
        async for chunk in stream_response(prompt):
            if chunk:
                full_response += chunk
                yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
    except Exception as e:
        logger.error(f"LLM streaming failed: {e}")
        yield f"data: {json.dumps({'type': 'error', 'content': 'LLM stream failed.'})}\n\n"
        return

    # 4. Persist exchange to memory.
    await update_memory(
        session_id=request.session_id,
        query=request.query,
        response=full_response,
    )

    # 5. Signal completion.
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


@router.post("/chat")
async def chat_stream_endpoint(request: ChatRequest):
    """Streaming SSE endpoint for the Chat UI."""
    increment_counter("chat_stream_requests")
    return StreamingResponse(
        _build_streaming_chat(request),
        media_type="text/event-stream",
    )


@router.post("/chat/sync")
async def chat_sync_endpoint(request: ChatRequest):
    """Non-streaming synchronous endpoint. Uses run_chat (full LangGraph pipeline)."""
    increment_counter("chat_sync_requests")
    try:
        state = await run_chat(
            query=request.query,
            session_id=request.session_id,
            video_ids=request.video_ids,
        )

        if state.get("error") and not state.get("response"):
            raise HTTPException(status_code=400, detail=state["error"])

        formatted_citations = format_citations_for_response(state.get("citations", []))

        return {
            "response": state.get("response", ""),
            "intent": state.get("intent", ""),
            "citations": formatted_citations,
            "session_id": request.session_id,
        }
    except Exception as e:
        logger.error(f"Sync chat failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/chat/{session_id}")
async def clear_chat_memory(session_id: str):
    """Clear session memory."""
    await clear_memory(session_id)
    return {"status": "success", "message": f"Memory cleared for session {session_id}"}
