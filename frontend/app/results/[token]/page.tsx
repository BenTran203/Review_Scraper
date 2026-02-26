"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ProgressTracker } from "@/components/ProgressTracker";
import { ResultsSummary } from "@/components/ResultsSummary";
import { ProsConsCard } from "@/components/ProsConsCard";
import { SentimentChart } from "@/components/SentimentChart";
import { ReviewHighlights } from "@/components/ReviewHighlights";
import { getSession, AnalysisResult, SessionData } from "@/lib/api";
import { startHeartbeat } from "@/lib/session";
import { ArrowLeft } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

export default function ResultsPage() {
  const params = useParams();
  const token = params.token as string;

  const [status, setStatus] = useState("connecting");
  const [message, setMessage] = useState("Connecting...");
  const [session, setSession] = useState<SessionData | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState("");
  const heartbeatCleanup = useRef<(() => void) | null>(null);

  // Start heartbeat to keep session alive
  useEffect(() => {
    heartbeatCleanup.current = startHeartbeat(token);
    return () => {
      heartbeatCleanup.current?.();
    };
  }, [token]);

  // Connect to SSE stream for real-time progress
  const connectSSE = useCallback(() => {
    const url = `${API_URL}/api/analyze/${token}/stream`;
    const source = new EventSource(url);

    source.addEventListener("status", (event) => {
      const data = JSON.parse(event.data);
      setStatus(data.status);
      setMessage(data.message || "");

      // When complete, fetch full results
      if (data.status === "complete") {
        source.close();
        fetchResults();
      }

      if (data.status === "error") {
        source.close();
        setError(data.message || "An error occurred");
      }
    });

    source.onerror = () => {
      source.close();
      // Try fetching session directly in case SSE failed but processing completed
      fetchResults();
    };

    return source;
  }, [token]);

  const fetchResults = async () => {
    try {
      const data = await getSession(token);
      setSession(data.session);
      if (data.analysis) {
        setAnalysis(data.analysis);
        setStatus("complete");
        setMessage("Analysis complete!");
      } else if (data.session.status === "error") {
        setStatus("error");
        setError(data.session.error_message || "An error occurred");
      }
    } catch {
      setError("Failed to load results. The session may have expired.");
      setStatus("error");
    }
  };

  useEffect(() => {
    const source = connectSSE();
    return () => source.close();
  }, [connectSSE]);

  const isLoading = !["complete", "error"].includes(status);

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      {/* Header */}
      <div className="mb-8 flex items-center gap-4">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--card-border)] bg-[var(--card)] px-3 py-2 text-sm text-[var(--muted)] transition-colors hover:text-white"
        >
          <ArrowLeft className="h-4 w-4" />
          New Analysis
        </Link>
        {session && (
          <div className="text-sm text-[var(--muted)]">
            {session.platform && (
              <span className="rounded-md bg-[var(--accent)]/20 px-2 py-0.5 text-xs font-medium text-[var(--accent)]">
                {session.platform}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Progress */}
      {isLoading && <ProgressTracker status={status} message={message} />}

      {/* Error */}
      {status === "error" && (
        <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-6 text-center">
          <p className="text-red-400">{error}</p>
          <Link
            href="/"
            className="mt-4 inline-block rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white"
          >
            Try Again
          </Link>
        </div>
      )}

      {/* Results */}
      {status === "complete" && analysis && (
        <div className="space-y-6">
          <ResultsSummary summary={analysis.summary} language={analysis.language} />

          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <ProsConsCard type="pros" items={analysis.pros} />
            <ProsConsCard type="cons" items={analysis.cons} />
          </div>

          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <SentimentChart sentiment={analysis.sentiment} />
            <ReviewHighlights keywords={analysis.keywords} />
          </div>
        </div>
      )}
    </main>
  );
}
