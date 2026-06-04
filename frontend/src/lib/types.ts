/**
 * TypeScript interfaces matching backend Pydantic models.
 */

export interface VideoMetadata {
  video_id: string;
  video_hash: string;
  url: string;
  title: string;
  creator_name: string;
  views: number;
  likes: number;
  comments: number;
  follower_count: number;
  upload_date: string;
  hashtags: string[];
  duration: number;
  engagement_rate: number;
  hook_text: string;
  summary: string;
  platform: string;
  transcript_quality: number;
  transcript_source?: "api" | "fallback" | "none" | string;
  ingested_at: string;
}

export interface AnalysisResult {
  engagement_gap: number;
  creator_size_ratio: number;
  duration_gap: number;
  hook_similarity: number;
  hashtag_overlap: number;
  question_count_a: number;
  question_count_b: number;
  cta_count_a: number;
  cta_count_b: number;
}

export interface Citation {
  video_name: string;
  chunk_id: string;
  timestamp: string;
  text_snippet: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  intent?: string;
  analysis?: AnalysisResult;
  citations?: Citation[];
  timestamp: Date;
}

// Issue 8 fix: added "refreshed" and "refresh_failed" to match all statuses
// the backend ingest router can now return.
export interface IngestionResponse {
  video_id: string;
  title: string;
  status: "success" | "already_exists" | "failed" | "partial_success" | "refreshed" | "refresh_failed";
  message: string;
  transcript_quality: number;
}

// Issue 7 fix: split the ambiguous `data` union into typed optional fields.
// Each SSE event type carries only the fields it actually sends, so
// ChatInterface never needs unsafe `as` type assertions.
export interface SSEEvent {
  type: "intent" | "analysis" | "citations" | "token" | "done" | "error" | "metadata";
  // intent event fields
  intent?: string;
  confidence?: number;
  // analysis event fields
  analysis?: AnalysisResult;
  // citations event fields
  citations?: Citation[];
  // metadata event fields
  videos?: VideoMetadata[];
  // token / error event fields
  content?: string;
}
