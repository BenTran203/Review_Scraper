"use client";

import { Tag } from "lucide-react";

interface ReviewHighlightsProps {
  keywords: string[];
}

export function ReviewHighlights({ keywords }: ReviewHighlightsProps) {
  return (
    <div className="rounded-2xl border border-[var(--card-border)] bg-[var(--card)] p-6">
      <div className="mb-4 flex items-center gap-2">
        <Tag className="h-5 w-5 text-[var(--accent)]" />
        <h2 className="text-lg font-semibold">Key Topics</h2>
      </div>

      <div className="flex flex-wrap gap-2">
        {keywords.map((keyword, i) => (
          <span
            key={i}
            className="inline-flex rounded-full border border-[var(--card-border)] bg-[var(--background)] px-3 py-1.5 text-sm text-[var(--foreground)] transition-colors hover:border-[var(--accent)] hover:text-[var(--accent)]"
          >
            {keyword}
          </span>
        ))}
      </div>

      {keywords.length === 0 && (
        <p className="text-sm text-[var(--muted)]">No keywords extracted.</p>
      )}
    </div>
  );
}
