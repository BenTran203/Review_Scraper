"use client";

import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from "recharts";
import { BarChart3 } from "lucide-react";

interface SentimentChartProps {
  sentiment: {
    positive: number;
    neutral: number;
    negative: number;
  };
}

const COLORS = {
  positive: "#22c55e",
  neutral: "#f59e0b",
  negative: "#ef4444",
};

export function SentimentChart({ sentiment }: SentimentChartProps) {
  const total = sentiment.positive + sentiment.neutral + sentiment.negative;
  const data = [
    { name: "Positive", value: sentiment.positive, color: COLORS.positive },
    { name: "Neutral", value: sentiment.neutral, color: COLORS.neutral },
    { name: "Negative", value: sentiment.negative, color: COLORS.negative },
  ].filter((d) => d.value > 0);

  return (
    <div className="rounded-2xl border border-[var(--card-border)] bg-[var(--card)] p-6">
      <div className="mb-4 flex items-center gap-2">
        <BarChart3 className="h-5 w-5 text-[var(--accent)]" />
        <h2 className="text-lg font-semibold">Sentiment</h2>
        <span className="ml-auto text-sm text-[var(--muted)]">
          {total} reviews
        </span>
      </div>

      <div className="h-52">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={50}
              outerRadius={80}
              paddingAngle={4}
              dataKey="value"
            >
              {data.map((entry, index) => (
                <Cell key={index} fill={entry.color} stroke="transparent" />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                background: "#111118",
                border: "1px solid #1e1e2e",
                borderRadius: "8px",
                fontSize: "12px",
              }}
            />
            <Legend
              formatter={(value: string) => (
                <span className="text-xs text-[var(--foreground)]">{value}</span>
              )}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>

      {/* Percentage bars */}
      <div className="mt-2 space-y-2">
        {data.map((d) => (
          <div key={d.name} className="flex items-center gap-3 text-xs">
            <span className="w-16 text-[var(--muted)]">{d.name}</span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[var(--background)]">
              <div
                className="h-full rounded-full transition-all"
                style={{
                  width: `${total > 0 ? (d.value / total) * 100 : 0}%`,
                  backgroundColor: d.color,
                }}
              />
            </div>
            <span className="w-8 text-right text-[var(--muted)]">
              {total > 0 ? Math.round((d.value / total) * 100) : 0}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
