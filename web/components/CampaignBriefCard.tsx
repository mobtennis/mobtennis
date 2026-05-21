"use client";

import { useState } from "react";

import type { CampaignBrief } from "@/lib/api";

const SITE_BASE = "https://mob.tennis";

/**
 * Build the UTM-tagged Final URL the operator pastes into Google Ads.
 *
 * Why a derived field rather than a stored field: the brief's
 * landing_path stays clean for audit (re-running the digest with a
 * different prompt shouldn't churn UTM data), and the UTM values are
 * predictable — anyone reading the dashboards can reconstruct them
 * from `<theme>` + `<week>`.
 *
 * The `utm_campaign` is `<week>-<slugified-theme>` so PostHog cohorts
 * are filterable by campaign. The `$initial_utm_*` person properties
 * PostHog captures on first visit then attribute every subsequent
 * event (return visit, follow, digest open) back to the originating
 * campaign — which is the whole point of doing this BEFORE spending.
 */
export function buildCampaignUrl(brief: CampaignBrief, weekStart: string): string {
  const themeSlug = brief.theme
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 40);
  const params = new URLSearchParams({
    utm_source: "google",
    utm_medium: "cpc",
    utm_campaign: `${weekStart}-${themeSlug}`,
  });
  return `${SITE_BASE}${brief.landing_path}?${params.toString()}`;
}

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
export function CampaignBriefCard({
  brief,
  weekStart,
}: {
  brief: CampaignBrief;
  /** ISO Monday of the digest week — feeds into the utm_campaign tag. */
  weekStart: string;
}) {
  const campaignUrl = buildCampaignUrl(brief, weekStart);
  return (
    <section className="rounded-lg border border-ink-700 bg-ink-900 p-5 shadow-card">
      <header className="flex items-baseline justify-between gap-3">
        <h2 className="text-base font-semibold tracking-tight text-text-primary">
          {brief.theme}
        </h2>
        <a
          href={campaignUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="shrink-0 text-xs font-medium text-accent hover:text-accent-dim"
        >
          Preview →
        </a>
      </header>

      <p className="mt-1 text-sm text-text-secondary">{brief.rationale}</p>

      <FinalUrlBlock url={campaignUrl} />
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


/** Final URL — what the operator pastes into Google Ads' "Final URL"
 * field for this ad group. Pre-tagged with UTM so PostHog can attribute
 * the click and every subsequent action from that visitor. */
function FinalUrlBlock({ url }: { url: string }) {
  const [copied, setCopied] = useState(false);
  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard rejected — operator can select-and-copy from the
      // rendered URL below.
    }
  };
  return (
    <div className="mt-4">
      <div className="flex items-center justify-between">
        <h3 className="text-[10px] font-bold uppercase tracking-wider text-text-muted">
          Final URL (UTM-tagged)
        </h3>
        <button
          onClick={onCopy}
          className="rounded-full border border-ink-700 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-text-secondary hover:border-ink-600 hover:text-accent"
        >
          {copied ? "Copied" : "Copy URL"}
        </button>
      </div>
      <div className="mt-2 break-all rounded-md border border-ink-700 bg-ink-900 px-3 py-2 text-xs text-text-primary">
        {url}
      </div>
    </div>
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
