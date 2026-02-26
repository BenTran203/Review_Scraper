"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { UrlInput } from "@/components/UrlInput";
import { LanguageSelector } from "@/components/LanguageSelector";
import { analyzeUrl } from "@/lib/api";
import { getOrCreateToken } from "@/lib/session";
import { Sparkles, ShieldCheck, Globe, AlertTriangle } from "lucide-react";

export default function HomePage() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [language, setLanguage] = useState("en");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleAnalyze = async () => {
    if (!url.trim()) {
      setError("Please paste a product URL");
      return;
    }

    setError("");
    setLoading(true);

    try {
      const sessionToken = await getOrCreateToken();
      const data = await analyzeUrl(url, language, sessionToken);
      router.push(`/results/${data.token}`);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to start analysis";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-4 py-16">
      {/* Hero */}
      <div className="mb-12 text-center">
        <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-[var(--card-border)] bg-[var(--card)] px-4 py-1.5 text-sm text-[var(--muted)]">
          <Sparkles className="h-4 w-4 text-[var(--accent)]" />
          AI-Powered Review Analytics
        </div>
        <h1 className="mb-4 text-4xl font-bold tracking-tight sm:text-5xl">
          ReviewPulse{" "}
          <span className="text-[var(--accent)]">AI</span>
        </h1>
        <p className="mx-auto max-w-lg text-lg text-[var(--muted)]">
          Paste a product URL from Amazon, Shopee, eBay, Lazada, or Tiki.
          Get an instant AI summary of customer reviews with pros, cons, and
          sentiment analysis.
        </p>
      </div>

      {/* Input Card */}
      <div className="w-full max-w-2xl rounded-2xl border border-[var(--card-border)] bg-[var(--card)] p-6 shadow-xl sm:p-8">
        <UrlInput value={url} onChange={setUrl} disabled={loading} />

        <div className="mt-4 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <LanguageSelector value={language} onChange={setLanguage} />

          <button
            onClick={handleAnalyze}
            disabled={loading || !url.trim()}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-[var(--accent)] px-6 py-3 font-semibold text-white transition-colors hover:bg-[var(--accent-hover)] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? (
              <>
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                Analyzing…
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" />
                Analyze Reviews
              </>
            )}
          </button>
        </div>

        {error && (
          <div className="mt-4 flex items-center gap-2 rounded-lg bg-red-500/10 px-4 py-3 text-sm text-red-400">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            {error}
          </div>
        )}
      </div>

      {/* Features */}
      <div className="mt-16 grid w-full max-w-3xl grid-cols-1 gap-6 sm:grid-cols-3">
        <FeatureCard
          icon={<Sparkles className="h-5 w-5 text-[var(--accent)]" />}
          title="AI Summary"
          description="GPT-4o-mini extracts pros, cons, and sentiment from real reviews."
        />
        <FeatureCard
          icon={<Globe className="h-5 w-5 text-[var(--accent)]" />}
          title="Multi-Language"
          description="Get results in English, Vietnamese, Spanish, or Japanese."
        />
        <FeatureCard
          icon={<ShieldCheck className="h-5 w-5 text-[var(--accent)]" />}
          title="Privacy First"
          description="No personal data stored. Sessions auto-expire after 1 hour."
        />
      </div>

      {/* Legal Disclaimer */}
      <p className="mt-12 max-w-lg text-center text-xs text-[var(--muted)]">
        ReviewPulse AI respects robots.txt, rate-limits requests, and strips
        personally identifiable information. Results are for informational
        purposes only and may not reflect all customer opinions.
        <br />
        Side note: Only Amazon and Lazada is available for scraping, other e-commerece still not available due to heavily restriction on bot scraping
      </p>
    </main>
  );
}

function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-xl border border-[var(--card-border)] bg-[var(--card)] p-5">
      <div className="mb-3">{icon}</div>
      <h3 className="mb-1 font-semibold">{title}</h3>
      <p className="text-sm text-[var(--muted)]">{description}</p>
    </div>
  );
}
