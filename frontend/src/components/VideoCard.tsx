"use client";

import type { VideoMetadata } from "@/lib/types";
import { formatNumber, formatDuration } from "@/lib/api";

interface VideoCardProps {
  video: VideoMetadata;
  isSelected: boolean;
  onToggle: (videoId: string) => void;
}

export function VideoCard({ video, isSelected, onToggle }: VideoCardProps) {
  return (
    <button
      id={`video-card-${video.video_id}`}
      onClick={() => onToggle(video.video_id)}
      className={`glass-card p-4 w-full text-left transition-all duration-200 ${
        isSelected
          ? "border-indigo-500/40 bg-indigo-500/5 shadow-[0_0_16px_rgba(99,102,241,0.1)]"
          : ""
      }`}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <h4 className="text-sm font-medium text-[var(--text-primary)] leading-tight line-clamp-2">
          {video.title}
        </h4>
        <div
          className={`w-4 h-4 rounded-full border-2 flex-shrink-0 transition-all duration-200 mt-0.5 ${
            isSelected
              ? "border-indigo-400 bg-indigo-400"
              : "border-white/20"
          }`}
        >
          {isSelected && (
            <svg className="w-full h-full text-white p-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
            </svg>
          )}
        </div>
      </div>

      {/* Creator */}
      <p className="text-xs text-[var(--text-muted)] mb-3">
        {video.creator_name} · {formatDuration(video.duration)}
      </p>

      {/* Metrics row */}
      <div className="grid grid-cols-3 gap-2">
        <div className="metric-card !p-2">
          <div className="metric-value !text-base">{formatNumber(video.views)}</div>
          <div className="metric-label !text-[9px]">Views</div>
        </div>
        <div className="metric-card !p-2">
          <div className="metric-value !text-base">{video.engagement_rate}%</div>
          <div className="metric-label !text-[9px]">Engagement</div>
        </div>
        <div className="metric-card !p-2">
          <div className="metric-value !text-base">{formatNumber(video.likes)}</div>
          <div className="metric-label !text-[9px]">Likes</div>
        </div>
      </div>

      {/* Quality & Tags */}
      <div className="flex items-center gap-2 mt-3 flex-wrap">
        <span
          className={`badge ${
            video.transcript_quality >= 0.7
              ? "badge-success"
              : video.transcript_quality >= 0.4
              ? "badge-warning"
              : "badge-error"
          }`}
        >
          Quality {video.transcript_quality * 100}%
        </span>
        {video.hashtags.slice().map((tag) => (
          <span key={tag} className="text-[10px] text-[var(--text-muted)]">
            #{tag}
          </span>
        ))}
      </div>
    </button>
  );
}
