"use client";

import { useState, useEffect, useCallback } from "react";
import { ChatInterface } from "@/components/ChatInterface";
import { VideoIngest } from "@/components/VideoIngest";
import { VideoCard } from "@/components/VideoCard";
import { ComparisonDashboard } from "@/components/ComparisonDashboard";
import { listVideos } from "@/lib/api";
import type { VideoMetadata } from "@/lib/types";

const VIDEOS_CACHE_KEY = "rag_ingested_videos";
const SELECTED_IDS_KEY = "rag_selected_ids";

export default function Home() {
  const [videos, setVideos] = useState<VideoMetadata[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [fetchError, setFetchError] = useState(false);

  // Issue 1 fix: load cached videos and selections immediately on mount
  // so sidebar is not empty while the backend fetch is in-flight.
  useEffect(() => {
    try {
      const cached = localStorage.getItem(VIDEOS_CACHE_KEY);
      if (cached) setVideos(JSON.parse(cached));

      const savedIds = localStorage.getItem(SELECTED_IDS_KEY);
      if (savedIds) setSelectedIds(JSON.parse(savedIds));
    } catch {
      // localStorage unavailable or corrupt — start fresh
    }
  }, []);

  // Persist selected IDs whenever they change.
  useEffect(() => {
    try {
      localStorage.setItem(SELECTED_IDS_KEY, JSON.stringify(selectedIds));
    } catch {}
  }, [selectedIds]);

  const fetchVideos = useCallback(async () => {
    setFetchError(false);
    try {
      const data = await listVideos();
      setVideos(data);
      // Update cache with fresh data from the backend.
      try {
        localStorage.setItem(VIDEOS_CACHE_KEY, JSON.stringify(data));
      } catch {}
    } catch {
      // Issue 1 fix: don't wipe cached videos on error — show stale data
      // and surface a visible error indicator instead of an empty sidebar.
      setFetchError(true);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchVideos();
  }, [fetchVideos]);

  const toggleVideo = (videoId: string) => {
    setSelectedIds((prev) =>
      prev.includes(videoId)
        ? prev.filter((id) => id !== videoId)
        : [...prev, videoId]
    );
  };

  const selectedVideos = videos.filter((v) => selectedIds.includes(v.video_id));

  return (
    <div className="flex h-screen overflow-hidden">
      {/* ===== Sidebar ===== */}
      <aside
        className={`${
          sidebarOpen ? "w-[380px]" : "w-0"
        } flex-shrink-0 transition-all duration-300 overflow-hidden border-r border-white/[0.06] bg-[var(--bg-secondary)] flex flex-col`}
      >
        {/* Sidebar Header */}
        <div className="px-5 py-4 border-b border-white/[0.06] flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
              <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div>
              <h1 className="text-sm font-bold text-[var(--text-primary)]">
                Creator Intelligence
              </h1>
              <p className="text-[10px] text-[var(--text-muted)]">
                RAG-Powered Analysis
              </p>
            </div>
          </div>
        </div>

        {/* Sidebar Content — scrollable */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
          {/* Ingest Form */}
          <VideoIngest onIngested={fetchVideos} />

          {/* Video List */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider">
                Videos ({videos.length})
              </h3>
              {selectedIds.length > 0 && (
                <button
                  onClick={() => setSelectedIds([])}
                  className="text-[10px] text-indigo-400 hover:text-indigo-300 transition-colors"
                >
                  Clear selection
                </button>
              )}
            </div>

            {/* Issue 1 fix: show backend error without wiping the list */}
            {fetchError && (
              <p className="text-[10px] text-amber-400 mb-2 px-1">
                Could not reach backend — showing cached data
              </p>
            )}

            {isLoading && videos.length === 0 ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="skeleton h-32 w-full" />
                ))}
              </div>
            ) : videos.length === 0 ? (
              <div className="text-center py-8">
                <div className="w-12 h-12 rounded-xl bg-white/[0.03] flex items-center justify-center mx-auto mb-3">
                  <svg className="w-6 h-6 text-[var(--text-muted)]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                </div>
                <p className="text-sm text-[var(--text-muted)]">No videos yet</p>
                <p className="text-xs text-[var(--text-muted)] mt-1">
                  Paste a YouTube or Instagram URL above to get started
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {videos.map((video) => (
                  <VideoCard
                    key={video.video_id}
                    video={video}
                    isSelected={selectedIds.includes(video.video_id)}
                    onToggle={toggleVideo}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Comparison Dashboard — shows when 2+ videos selected */}
          {selectedVideos.length >= 2 && (
            <ComparisonDashboard
              videos={selectedVideos}
            />
          )}
        </div>

        {/* Sidebar Footer */}
        {selectedIds.length > 0 && (
          <div className="px-4 py-3 border-t border-white/[0.06] bg-indigo-500/5">
            <p className="text-xs text-indigo-300">
              <span className="font-semibold">{selectedIds.length}</span> video{selectedIds.length > 1 ? "s" : ""} selected for analysis
            </p>
          </div>
        )}
      </aside>

      {/* ===== Main Chat Panel ===== */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* Toggle sidebar button */}
        <div className="absolute top-4 left-2 z-10">
          <button
            id="toggle-sidebar-btn"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-2 rounded-lg bg-white/[0.03] hover:bg-white/[0.06] border border-white/[0.06] transition-all duration-200"
            title={sidebarOpen ? "Hide sidebar" : "Show sidebar"}
          >
            <svg
              className={`w-4 h-4 text-[var(--text-muted)] transition-transform duration-200 ${
                sidebarOpen ? "" : "rotate-180"
              }`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
            </svg>
          </button>
        </div>

        <ChatInterface videoIds={selectedIds} />
      </main>
    </div>
  );
}
