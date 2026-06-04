"use client";

import { useState } from "react";
import type { Citation } from "@/lib/types";

interface CitationBlockProps {
  citation: Citation;
  index: number;
}

export function CitationBlock({ citation, index }: CitationBlockProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div 
      className={`citation-block cursor-pointer transition-all duration-200 border ${isExpanded ? 'border-indigo-500/40 bg-white/[0.03]' : 'border-white/5 hover:border-indigo-500/20'}`}
      onClick={() => setIsExpanded(!isExpanded)}
      title="Click to expand full transcript chunk"
    >
      <div className="flex items-center gap-2 mb-2">
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
      
      <p className={`text-xs text-[var(--text-secondary)] leading-relaxed transition-all ${!isExpanded ? 'line-clamp-2' : ''}`}>
        {citation.text_snippet}
      </p>
      
      <div className="flex justify-between items-center mt-2">
        <span className="text-[9px] text-[var(--text-muted)] font-mono">
          {citation.chunk_id}
        </span>
        <span className="text-[10px] text-indigo-400/70 select-none">
          {isExpanded ? "Show less ↑" : "Read more ↓"}
        </span>
      </div>
    </div>
  );
}
