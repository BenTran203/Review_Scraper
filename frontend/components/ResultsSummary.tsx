"use client";

import { SUPPORTED_LANGUAGES } from "@/lib/languages";
import { FileText, Globe } from "lucide-react";

interface ResultsSummaryProps {
  summary: string;
  language: string;
}

export function ResultsSummary({ summary, language }: ResultsSummaryProps) {
  const lang = SUPPORTED_LANGUAGES.find((l) => l.code === language);

  return (
    <div className="rounded-2xl border border-[var(--card-border)] bg-[var(--card)] p-6">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FileText className="h-5 w-5 text-[var(--accent)]" />
          <h2 className="text-lg font-semibold">Summary</h2>
        </div>
        {lang && (
          <span className="inline-flex items-center gap-1.5 rounded-md bg-[var(--accent)]/10 px-2.5 py-1 text-xs font-medium text-[var(--accent)]">
            <Globe className="h-3 w-3" />
            {lang.flag} {lang.label}
          </span>
        )}
      </div>
      <p className="leading-relaxed text-[var(--foreground)]">{summary}</p>
    </div>
  );
}
