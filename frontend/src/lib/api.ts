/**
 * API client for the Creator Intelligence RAG Platform.
 * Handles video ingestion, listing, and SSE streaming chat.
 */

import type {
  VideoMetadata,
  IngestionResponse,
  SSEEvent,
  ChatMessage,
  AnalysisResult,
  Citation,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Ingest a video URL.
 */
export async function ingestVideo(url: string, forceRefresh: boolean = false): Promise<IngestionResponse> {
  const res = await fetch(`${API_BASE}/api/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, force_refresh: forceRefresh }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Ingestion failed" }));
    throw new Error(err.detail || "Ingestion failed");
  }

  return res.json();
}

/**
 * List all ingested videos.
 */
export async function listVideos(): Promise<VideoMetadata[]> {
  const res = await fetch(`${API_BASE}/api/videos`);
  if (!res.ok) throw new Error("Failed to fetch videos");
  const data = await res.json();
  return data.videos || [];
}

/**
 * Get a single video by ID.
 */
export async function getVideo(videoId: string): Promise<VideoMetadata> {
  const res = await fetch(`${API_BASE}/api/videos/${videoId}`);
  if (!res.ok) throw new Error("Video not found");
  return res.json();
}

/**
 * SSE streaming chat.
 * Returns an async generator yielding SSE events.
 */
export async function* streamChat(
  query: string,
  sessionId: string = "default",
  videoIds: string[] = []
): AsyncGenerator<SSEEvent> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query,
      session_id: sessionId,
      video_ids: videoIds,
    }),
  });

  if (!res.ok) {
    throw new Error("Chat request failed");
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          const event: SSEEvent = JSON.parse(line.slice(6));
          yield event;
        } catch {
          // Skip malformed lines
        }
      }
    }
  }
}

/**
 * Non-streaming chat (for testing / fallback).
 */
export async function chatSync(
  query: string,
  sessionId: string = "default",
  videoIds: string[] = []
): Promise<{
  intent: string;
  response: string;
  analysis: AnalysisResult | null;
  citations: Citation[];
}> {
  const res = await fetch(`${API_BASE}/api/chat/sync`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query,
      session_id: sessionId,
      video_ids: videoIds,
    }),
  });

  if (!res.ok) throw new Error("Chat failed");
  return res.json();
}

/**
 * Clear session memory.
 */
export async function clearSession(sessionId: string): Promise<void> {
  await fetch(`${API_BASE}/api/chat/${sessionId}`, { method: "DELETE" });
}

/**
 * Get pipeline metrics.
 */
export async function getMetrics(): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE}/api/metrics`);
  if (!res.ok) throw new Error("Failed to fetch metrics");
  return res.json();
}

/**
 * Format a number with commas.
 */
export function formatNumber(num: number): string {
  return num.toLocaleString();
}

/**
 * Format seconds as MM:SS or HH:MM:SS.
 */
export function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  return `${m}:${s.toString().padStart(2, "0")}`;
}
