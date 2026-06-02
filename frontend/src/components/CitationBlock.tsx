"use client";

import type { Citation } from "@/lib/types";

interface CitationBlockProps {
  citation: Citation;
  index: number;
}

export function CitationBlock({ citation, index }: CitationBlockProps) {
  return (
    <div className="citation-block">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-[10px] font-bold text-indigo-400 bg-indigo-500/10 rounded px-1.5 py-0.5">
          [{index}]
        </span>
        <span className="text-xs font-medium text-[var(--text-primary)]">
          {citation.video_name}
        </span>
        {citation.timestamp && (
          <span className="text-[10px] text-[var(--text-muted)] ml-auto font-mono">
            ⏱ {citation.timestamp}
          </span>
        )}
      </div>
      <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
        {citation.text_snippet}
      </p>
      <span className="text-[9px] text-[var(--text-muted)] mt-1 inline-block">
        {citation.chunk_id}
      </span>
    </div>
  );
}
