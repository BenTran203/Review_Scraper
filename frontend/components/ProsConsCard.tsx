"use client";

import { ThumbsUp, ThumbsDown } from "lucide-react";

interface ProsConsCardProps {
  type: "pros" | "cons";
  items: string[];
}

export function ProsConsCard({ type, items }: ProsConsCardProps) {
  const isPros = type === "pros";

  return (
    <div className="rounded-2xl border border-[var(--card-border)] bg-[var(--card)] p-6">
      <div className="mb-4 flex items-center gap-2">
        {isPros ? (
          <ThumbsUp className="h-5 w-5 text-[var(--success)]" />
        ) : (
          <ThumbsDown className="h-5 w-5 text-[var(--danger)]" />
        )}
        <h2 className="text-lg font-semibold">
          {isPros ? "Pros" : "Cons"}
        </h2>
        <span className="ml-auto rounded-full bg-[var(--background)] px-2.5 py-0.5 text-xs text-[var(--muted)]">
          {items.length}
        </span>
      </div>
      <ul className="space-y-3">
        {items.map((item, i) => (
          <li key={i} className="flex items-start gap-3 text-sm">
            <span
              className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${
                isPros ? "bg-[var(--success)]" : "bg-[var(--danger)]"
              }`}
            />
            <span className="text-[var(--foreground)]">{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
