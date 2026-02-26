"use client";

import { detectPlatform } from "@/lib/platforms";
import { Link2, Store } from "lucide-react";

interface UrlInputProps {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}

export function UrlInput({ value, onChange, disabled }: UrlInputProps) {
  const platform = detectPlatform(value);

  return (
    <div>
      <label
        htmlFor="product-url"
        className="mb-2 block text-sm font-medium text-[var(--muted)]"
      >
        Product URL
      </label>
      <div className="relative">
        <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-4">
          <Link2 className="h-5 w-5 text-[var(--muted)]" />
        </div>
        <input
          id="product-url"
          type="url"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          placeholder="https://www.amazon.com/dp/B0... or any supported store URL"
          className="w-full rounded-xl border border-[var(--card-border)] bg-[var(--background)] py-3.5 pl-12 pr-4 text-white placeholder-[var(--muted)] transition-colors focus:border-[var(--accent)] focus:outline-none disabled:opacity-50"
        />
        {platform && (
          <div className="absolute inset-y-0 right-0 flex items-center pr-4">
            <span className="inline-flex items-center gap-1.5 rounded-md bg-[var(--accent)]/20 px-2.5 py-1 text-xs font-medium text-[var(--accent)]">
              <Store className="h-3 w-3" />
              {platform}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
