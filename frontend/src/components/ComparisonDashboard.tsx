"use client";

import type { VideoMetadata } from "@/lib/types";
import { formatNumber, formatDuration } from "@/lib/api";

interface ComparisonDashboardProps {
  videoA: VideoMetadata;
  videoB: VideoMetadata;
}

interface MetricCompareProps {
  label: string;
  valueA: number;
  valueB: number;
  formatter?: (v: number) => string;
  suffix?: string;
  higherIsBetter?: boolean;
}

function MetricCompare({
  label,
  valueA,
  valueB,
  formatter = (v) => formatNumber(v),
  suffix = "",
  higherIsBetter = true,
}: MetricCompareProps) {
  const maxVal = Math.max(valueA, valueB, 1);
  const pctA = (valueA / maxVal) * 100;
  const pctB = (valueB / maxVal) * 100;

  const aWins = higherIsBetter ? valueA > valueB : valueA < valueB;
  const bWins = higherIsBetter ? valueB > valueA : valueB < valueA;

  return (
    <div className="space-y-1.5">
      <div className="flex justify-between items-center text-xs">
        <span className="text-[var(--text-muted)]">{label}</span>
      </div>
      <div className="flex items-center gap-3">
        {/* Video A */}
        <div className="flex-1 text-right">
          <span
            className={`text-sm font-semibold ${
              aWins ? "text-indigo-400" : "text-[var(--text-secondary)]"
            }`}
          >
            {formatter(valueA)}{suffix}
          </span>
        </div>

        {/* Bar */}
        <div className="w-32 flex-shrink-0">
          <div className="comparison-bar">
            <div
              className="comparison-bar-fill-a"
              style={{ width: `${pctA}%` }}
            />
          </div>
          <div className="comparison-bar mt-0.5">
            <div
              className="comparison-bar-fill-b"
              style={{ width: `${pctB}%` }}
            />
          </div>
        </div>

        {/* Video B */}
        <div className="flex-1">
          <span
            className={`text-sm font-semibold ${
              bWins ? "text-purple-400" : "text-[var(--text-secondary)]"
            }`}
          >
            {formatter(valueB)}{suffix}
          </span>
        </div>
      </div>
    </div>
  );
}

export function ComparisonDashboard({ videoA, videoB }: ComparisonDashboardProps) {
  // Compute hashtag overlap (Jaccard)
  const setA = new Set(videoA.hashtags.map((h) => h.toLowerCase()));
  const setB = new Set(videoB.hashtags.map((h) => h.toLowerCase()));
  const intersection = new Set([...setA].filter((x) => setB.has(x)));
  const union = new Set([...setA, ...setB]);
  const hashtagOverlap = union.size > 0 ? intersection.size / union.size : 0;

  return (
    <div className="glass-card p-5 animate-fade-in">
      <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-4 flex items-center gap-2">
        <svg className="w-4 h-4 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
        Comparison Dashboard
      </h3>

      {/* Video labels */}
      <div className="flex justify-between items-center mb-4 px-1">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-indigo-500" />
          <span className="text-xs text-[var(--text-secondary)] truncate max-w-[120px]">
            {videoA.title}
          </span>
        </div>
        <span className="text-[10px] text-[var(--text-muted)]">vs</span>
        <div className="flex items-center gap-2">
          <span className="text-xs text-[var(--text-secondary)] truncate max-w-[120px] text-right">
            {videoB.title}
          </span>
          <div className="w-3 h-3 rounded-full bg-purple-500" />
        </div>
      </div>

      {/* Metric comparisons */}
      <div className="space-y-4">
        <MetricCompare label="Views" valueA={videoA.views} valueB={videoB.views} />
        <MetricCompare
          label="Engagement Rate"
          valueA={videoA.engagement_rate}
          valueB={videoB.engagement_rate}
          formatter={(v) => v.toFixed(2)}
          suffix="%"
        />
        <MetricCompare label="Likes" valueA={videoA.likes} valueB={videoB.likes} />
        <MetricCompare label="Comments" valueA={videoA.comments} valueB={videoB.comments} />
        <MetricCompare label="Followers" valueA={videoA.follower_count} valueB={videoB.follower_count} />
        <MetricCompare
          label="Duration"
          valueA={videoA.duration}
          valueB={videoB.duration}
          formatter={(v) => formatDuration(v)}
          higherIsBetter={false}
        />
      </div>

      {/* Hashtag overlap */}
      <div className="mt-4 pt-4 border-t border-white/[0.06]">
        <div className="flex justify-between items-center mb-2">
          <span className="text-xs text-[var(--text-muted)]">Hashtag Overlap</span>
          <span className="text-sm font-semibold text-[var(--text-primary)]">
            {(hashtagOverlap * 100).toFixed(0)}%
          </span>
        </div>
        <div className="progress-bar">
          <div
            className="progress-fill"
            style={{ width: `${hashtagOverlap * 100}%` }}
          />
        </div>
        {intersection.size > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {[...intersection].map((tag) => (
              <span key={tag} className="text-[10px] text-indigo-300 bg-indigo-500/10 px-1.5 py-0.5 rounded">
                #{tag}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
