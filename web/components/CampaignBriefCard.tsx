"use client";

import { useState } from "react";

import type { CampaignBrief } from "@/lib/api";

/**
 * Renders one campaign brief with copy-to-clipboard buttons for the
 * three blocks that go into Google Ads: keywords (one per line),
 * headlines (one per line), descriptions (one per line). The operator
 * pastes each block into the corresponding field in the Ads UI.
 *
 * Char-count badges next to each headline/description make any
 * over-limit items visually obvious — the LLM is constrained to 30/90
 * but truncation can produce ugly results when it tries to fit.
 */
export function CampaignBriefCard({ brief }: { brief: CampaignBrief }) {
  return (
    <section className="rounded-lg border border-ink-700 bg-ink-900 p-5 shadow-card">
      <header className="flex items-baseline justify-between gap-3">
        <h2 className="text-base font-semibold tracking-tight text-text-primary">
          {brief.theme}
        </h2>
        <a
          href={brief.landing_path}
          target="_blank"
          rel="noopener noreferrer"
          className="shrink-0 text-xs font-medium text-accent hover:text-accent-dim"
        >
          {brief.landing_path} →
        </a>
      </header>

      <p className="mt-1 text-sm text-text-secondary">{brief.rationale}</p>

      <Block
        label="Keywords"
        items={brief.keywords}
        joiner="\n"
        showLength={false}
      />
      <Block
        label={`Ad headlines (≤ 30 chars)`}
        items={brief.ad_headlines}
        joiner="\n"
        showLength={30}
      />
      <Block
        label={`Ad descriptions (≤ 90 chars)`}
        items={brief.ad_descriptions}
        joiner="\n"
        showLength={90}
      />
    </section>
  );
}

function Block({
  label,
  items,
  joiner,
  showLength,
}: {
  label: string;
  items: string[];
  joiner: string;
  /** Numeric = char limit (render count badge); false = hide. */
  showLength: number | false;
}) {
  const [copied, setCopied] = useState(false);
  const onCopy = async () => {
    try {
      // The joiner string is provided as a literal "\n" so it survives
      // the JSX prop, but we want a real newline in the clipboard.
      const blob = items.join(joiner.replace(/\\n/g, "\n"));
      await navigator.clipboard.writeText(blob);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Ignore — clipboard rejected (insecure context, perms). Operator
      // can select-and-copy from the rendered list manually.
    }
  };

  return (
    <div className="mt-4">
      <div className="flex items-center justify-between">
        <h3 className="text-[10px] font-bold uppercase tracking-wider text-text-muted">
          {label}
        </h3>
        <button
          onClick={onCopy}
          className="rounded-full border border-ink-700 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-text-secondary hover:border-ink-600 hover:text-accent"
        >
          {copied ? "Copied" : "Copy all"}
        </button>
      </div>
      <ul className="mt-2 divide-y divide-ink-700/40 overflow-hidden rounded-md border border-ink-700 bg-ink-900">
        {items.map((s, i) => {
          const len = s.length;
          const over = typeof showLength === "number" && len > showLength;
          return (
            <li
              key={i}
              className="flex items-center justify-between gap-3 px-3 py-2 text-sm"
            >
              <span className="min-w-0 flex-1 truncate text-text-primary">
                {s}
              </span>
              {showLength !== false && (
                <span
                  className={`shrink-0 text-[10px] tnum ${
                    over ? "font-bold text-live" : "text-text-muted"
                  }`}
                >
                  {len}/{showLength}
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
