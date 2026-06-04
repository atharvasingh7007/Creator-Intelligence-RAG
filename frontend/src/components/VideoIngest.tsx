"use client";

import { useState } from "react";
import { ingestVideo } from "@/lib/api";
import type { IngestionResponse } from "@/lib/types";

interface VideoIngestProps {
  onIngested: () => void;
}

export function VideoIngest({ onIngested }: VideoIngestProps) {
  const [url, setUrl] = useState("");
  const [forceRefresh, setForceRefresh] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<IngestionResponse | null>(null);
  const [error, setError] = useState("");
  const [forceRefresh, setForceRefresh] = useState(false);

  const detectPlatform = (url: string): string => {
    if (url.includes("youtube.com") || url.includes("youtu.be")) return "YouTube";
    if (url.includes("instagram.com")) return "Instagram";
    return "Video";
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedUrl = url.trim();
    if (!trimmedUrl) return;

    setIsLoading(true);
    setResult(null);
    setError("");

    try {
      const response = await ingestVideo(trimmedUrl, forceRefresh);
      setResult(response);
      // Issues 3 & 8 fix: call onIngested for all non-failed statuses
      // so the sidebar refreshes after refresh, partial_success, etc.
      const successStatuses = ["success", "already_exists", "refreshed", "partial_success"];
      if (successStatuses.includes(response.status)) {
        onIngested();
        setUrl("");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ingestion failed");
    } finally {
      setIsLoading(false);
    }
  };

  // Issue 3 & 8 fix: resolve styling and icon for every possible status.
  const getStatusStyle = (status: string) => {
    switch (status) {
      case "success":
        return "bg-emerald-500/10 border border-emerald-500/20 text-emerald-300";
      case "already_exists":
        return "bg-amber-500/10 border border-amber-500/20 text-amber-300";
      case "refreshed":
        return "bg-blue-500/10 border border-blue-500/20 text-blue-300";
      case "partial_success":
        return "bg-yellow-500/10 border border-yellow-500/20 text-yellow-300";
      case "refresh_failed":
        return "bg-orange-500/10 border border-orange-500/20 text-orange-300";
      default:
        return "bg-red-500/10 border border-red-500/20 text-red-300";
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "success": return "✓ ";
      case "already_exists": return "↻ ";
      case "refreshed": return "↺ ";
      case "partial_success": return "~ ";
      case "refresh_failed": return "⚠ ";
      default: return "✕ ";
    }
  };

  const getQualityLabel = (status: string, quality: number) => {
    if (status === "success" || status === "partial_success") {
      return `Transcript: ${Math.round(quality * 100)}%`;
    }
    if (status === "already_exists" || status === "refreshed") {
      return quality > 0
        ? `Transcript: ${Math.round(quality * 100)}%`
        : "No transcript";
    }
    return "";
  };

  return (
    <div className="glass-card p-5">
      <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
        <svg className="w-4 h-4 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
        </svg>
        Ingest Video
      </h3>

      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="relative">
          <input
            id="video-url-input"
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="Paste YouTube or Instagram URL..."
            className="input-field pr-20"
            disabled={isLoading}
          />
          {url && (
            <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] badge badge-info">
              {detectPlatform(url)}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2 pl-1 mb-2">
          <input
            id="force-refresh-checkbox"
            type="checkbox"
            checked={forceRefresh}
            onChange={(e) => setForceRefresh(e.target.checked)}
            className="w-3.5 h-3.5 rounded border-white/[0.1] bg-white/[0.03] text-indigo-500 focus:ring-indigo-500/20"
            disabled={isLoading}
          />
          <label htmlFor="force-refresh-checkbox" className="text-xs text-[var(--text-muted)] cursor-pointer select-none">
            Force re-ingest (bypass cache)
          </label>
        </div>

        <button
          id="ingest-btn"
          type="submit"
          disabled={isLoading || !url.trim()}
          className="btn-primary w-full text-sm"
        >
          {isLoading ? (
            <span className="flex items-center justify-center gap-2">
              <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Processing...
            </span>
          ) : (
            "Ingest Video"
          )}
        </button>

        <div className="flex items-center gap-2 mt-2 ml-1">
          <input
            type="checkbox"
            id="forceRefresh"
            checked={forceRefresh}
            onChange={(e) => setForceRefresh(e.target.checked)}
            className="w-3.5 h-3.5 rounded border-gray-600 bg-white/5 text-indigo-500 focus:ring-indigo-500/30"
          />
          <label htmlFor="forceRefresh" className="text-xs text-[var(--text-secondary)] select-none cursor-pointer">
            Force Full Re-Ingest (Clear Cache)
          </label>
        </div>
      </form>

      {/* Result feedback */}
      {result && (
        <div className={`mt-3 p-3 rounded-lg text-sm animate-fade-in ${getStatusStyle(result.status)}`}>
          <p className="font-medium">
            {getStatusIcon(result.status)}
            {result.title || "Video"}
          </p>
          <p className="text-xs mt-1 opacity-80">
            {result.message}
            {getQualityLabel(result.status, result.transcript_quality) && (
              <span className="ml-2 opacity-70">
                • {getQualityLabel(result.status, result.transcript_quality)}
              </span>
            )}
          </p>
        </div>
      )}

      {error && (
        <div className="mt-3 p-3 rounded-lg text-sm bg-red-500/10 border border-red-500/20 text-red-300 animate-fade-in">
          ⚠️ {error}
        </div>
      )}
    </div>
  );
}
