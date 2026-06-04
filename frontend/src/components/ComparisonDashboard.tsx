import type { VideoMetadata } from "@/lib/types";
import { formatNumber, formatDuration } from "@/lib/api";

interface ComparisonDashboardProps {
  videos: VideoMetadata[];
}

export function ComparisonDashboard({ videos }: ComparisonDashboardProps) {
  if (!videos || videos.length < 2) return null;

  // Compute hashtag overlap (intersection of ALL selected videos)
  const tagSets = videos.map(v => new Set(v.hashtags.map(h => h.toLowerCase())));
  const intersection = tagSets.reduce((acc, set) => new Set([...acc].filter(x => set.has(x))));
  const union = new Set(tagSets.flatMap(set => [...set]));
  const hashtagOverlap = union.size > 0 ? intersection.size / union.size : 0;

  return (
    <div className="glass-card p-5 animate-fade-in overflow-x-auto">
      <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-4 flex items-center gap-2">
        <svg className="w-4 h-4 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
        Comparison Dashboard
      </h3>

      <div className="min-w-max">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-white/[0.06]">
              <th className="pb-2 font-medium text-[var(--text-muted)]">Metric</th>
              {videos.map((v) => (
                <th key={v.video_id} className="pb-2 px-3 font-semibold text-[var(--text-secondary)] max-w-[100px] truncate" title={v.title}>
                  {v.title}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.06]">
            <tr>
              <td className="py-2 text-[var(--text-muted)]">Views</td>
              {videos.map(v => <td key={v.video_id} className="py-2 px-3 text-[var(--text-primary)] font-medium">{formatNumber(v.views)}</td>)}
            </tr>
            <tr>
              <td className="py-2 text-[var(--text-muted)]">Engagement</td>
              {videos.map(v => <td key={v.video_id} className="py-2 px-3 text-[var(--text-primary)] font-medium">{v.engagement_rate.toFixed(2)}%</td>)}
            </tr>
            <tr>
              <td className="py-2 text-[var(--text-muted)]">Likes</td>
              {videos.map(v => <td key={v.video_id} className="py-2 px-3 text-[var(--text-primary)] font-medium">{formatNumber(v.likes)}</td>)}
            </tr>
            <tr>
              <td className="py-2 text-[var(--text-muted)]">Comments</td>
              {videos.map(v => <td key={v.video_id} className="py-2 px-3 text-[var(--text-primary)] font-medium">{formatNumber(v.comments)}</td>)}
            </tr>
            <tr>
              <td className="py-2 text-[var(--text-muted)]">Followers</td>
              {videos.map(v => <td key={v.video_id} className="py-2 px-3 text-[var(--text-primary)] font-medium">{formatNumber(v.follower_count)}</td>)}
            </tr>
            <tr>
              <td className="py-2 text-[var(--text-muted)]">Duration</td>
              {videos.map(v => <td key={v.video_id} className="py-2 px-3 text-[var(--text-primary)] font-medium">{formatDuration(v.duration)}</td>)}
            </tr>
          </tbody>
        </table>
      </div>

      {/* Hashtag overlap */}
      <div className="mt-4 pt-4 border-t border-white/[0.06]">
        <div className="flex justify-between items-center mb-2">
          <span className="text-xs text-[var(--text-muted)]">Shared Hashtag Overlap</span>
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
