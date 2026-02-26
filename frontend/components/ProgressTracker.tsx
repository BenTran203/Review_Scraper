"use client";

import { Loader2, Search, Brain, CheckCircle2 } from "lucide-react";

interface ProgressTrackerProps {
  status: string;
  message: string;
}

const STEPS = [
  { key: "scraping", label: "Scraping Reviews", icon: Search },
  { key: "analyzing", label: "AI Analysis", icon: Brain },
  { key: "complete", label: "Complete", icon: CheckCircle2 },
];

export function ProgressTracker({ status, message }: ProgressTrackerProps) {
  const currentIdx = STEPS.findIndex((s) => s.key === status);

  return (
    <div className="rounded-2xl border border-[var(--card-border)] bg-[var(--card)] p-8">
      {/* Steps */}
      <div className="mb-8 flex items-center justify-center gap-4">
        {STEPS.map((step, idx) => {
          const Icon = step.icon;
          const isActive = step.key === status;
          const isDone = currentIdx > idx;

          return (
            <div key={step.key} className="flex items-center gap-4">
              <div className="flex flex-col items-center gap-2">
                <div
                  className={`flex h-10 w-10 items-center justify-center rounded-full border-2 transition-all ${
                    isActive
                      ? "border-[var(--accent)] bg-[var(--accent)]/20 text-[var(--accent)]"
                      : isDone
                        ? "border-[var(--success)] bg-[var(--success)]/20 text-[var(--success)]"
                        : "border-[var(--card-border)] text-[var(--muted)]"
                  }`}
                >
                  {isActive ? (
                    <Loader2 className="h-5 w-5 animate-spin" />
                  ) : (
                    <Icon className="h-5 w-5" />
                  )}
                </div>
                <span
                  className={`text-xs font-medium ${
                    isActive
                      ? "text-[var(--accent)]"
                      : isDone
                        ? "text-[var(--success)]"
                        : "text-[var(--muted)]"
                  }`}
                >
                  {step.label}
                </span>
              </div>

              {idx < STEPS.length - 1 && (
                <div
                  className={`h-0.5 w-12 rounded-full ${
                    isDone ? "bg-[var(--success)]" : "bg-[var(--card-border)]"
                  }`}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Message */}
      <div className="flex items-center justify-center gap-2 text-sm text-[var(--muted)]">
        {status !== "complete" && status !== "error" && (
          <span className="animate-pulse-dot h-2 w-2 rounded-full bg-[var(--accent)]" />
        )}
        <span>{message || "Processing..."}</span>
      </div>
    </div>
  );
}
