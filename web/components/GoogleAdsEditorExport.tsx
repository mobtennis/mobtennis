"use client";

import { useState } from "react";

import type { CampaignBrief } from "@/lib/api";
import { buildCampaignUrl } from "@/components/CampaignBriefCard";

/**
 * Generates Google Ads Editor-compatible TSV blobs for the weekly
 * brief set, with one Copy button per entity type. The operator
 * downloads Google Ads Editor (free), opens their account, and uses
 * "Make multiple changes" → paste each block in order.
 *
 * Why one campaign with N ad groups (not N campaigns):
 *   - Single budget bucket — easier to compare ad-group cost/click
 *   - Networks / locations / bidding set once, can't drift between briefs
 *   - One place to pause if anything looks off
 *
 * Status: all entities default to Paused so the operator gets a final
 * visual review in Ads Editor before clicking "Post". This is the
 * safety gate we're keeping in v1.
 */
export function GoogleAdsEditorExport({
  briefs,
  weekStart,
}: {
  briefs: CampaignBrief[];
  weekStart: string;
}) {
  if (briefs.length === 0) return null;

  const campaignName = `mob.tennis - Week of ${weekStart}`;
  // Tomorrow → +14 days (matches the cron cadence — one cohort lives
  // through the following week's launch).
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  const endDate = new Date(tomorrow);
  endDate.setDate(endDate.getDate() + 13);
  const fmtDate = (d: Date) => d.toISOString().slice(0, 10);

  // Per Google Ads Editor's "Make multiple changes" docs, all fields
  // are TAB-separated and quoted only when containing the separator.
  // Locations use Google's named-location format; Ads Editor resolves
  // them to geo IDs at import time.
  const LOCATIONS =
    "United States;United Kingdom;Canada;Australia;Ireland;New Zealand";

  // ---- Campaign block --------------------------------------------------
  const campaignRows = [
    [
      "Campaign",
      "Campaign type",
      "Status",
      "Daily Budget",
      "Bid Strategy Type",
      "Default max. CPC",
      "Networks",
      "Languages",
      "Locations",
      "Start date",
      "End date",
    ],
    [
      campaignName,
      "Search",
      "Paused",
      "5.00",                 // USD; operator can bump after first day
      "Manual CPC",
      "0.30",
      "Google search",        // DELIBERATELY excludes Display + Search Partners
      "English",
      LOCATIONS,
      fmtDate(tomorrow),
      fmtDate(endDate),
    ],
  ];

  // ---- Ad group block --------------------------------------------------
  const adGroupRows = [
    ["Campaign", "Ad group", "Status", "Max CPC"],
    ...briefs.map((b) => [
      campaignName,
      b.theme,
      "Paused",
      "0.30",
    ]),
  ];

  // ---- Keywords block --------------------------------------------------
  // Phrase match (Google's "Phrase") rather than broad — keeps the
  // match-expansion that ate the previous campaign in check.
  const keywordRows: string[][] = [
    ["Campaign", "Ad group", "Keyword", "Match type", "Status"],
  ];
  for (const b of briefs) {
    for (const kw of b.keywords) {
      keywordRows.push([campaignName, b.theme, kw, "Phrase", "Paused"]);
    }
  }

  // ---- Ads block (Responsive Search Ads) ------------------------------
  // RSAs accept 3-15 headlines + 2-4 descriptions. Brief guarantees
  // 5-8 headlines and 2-4 descriptions post-validation, so we pad with
  // empty columns where the brief is short.
  const MAX_HEADLINES = 15;
  const MAX_DESCRIPTIONS = 4;
  const adHeader = [
    "Campaign",
    "Ad group",
    "Ad type",
    ...Array.from({ length: MAX_HEADLINES }, (_, i) => `Headline ${i + 1}`),
    ...Array.from({ length: MAX_DESCRIPTIONS }, (_, i) => `Description ${i + 1}`),
    "Final URL",
    "Status",
  ];
  const adRows: string[][] = [adHeader];
  for (const b of briefs) {
    const headlines = b.ad_headlines.slice(0, MAX_HEADLINES);
    while (headlines.length < MAX_HEADLINES) headlines.push("");
    const descriptions = b.ad_descriptions.slice(0, MAX_DESCRIPTIONS);
    while (descriptions.length < MAX_DESCRIPTIONS) descriptions.push("");
    adRows.push([
      campaignName,
      b.theme,
      "Responsive search ad",
      ...headlines,
      ...descriptions,
      buildCampaignUrl(b, weekStart),
      "Paused",
    ]);
  }

  return (
    <section className="rounded-lg border border-accent/40 bg-accent/5 p-5 shadow-card">
      <header>
        <h2 className="text-base font-semibold tracking-tight text-text-primary">
          Google Ads Editor bulk import
        </h2>
        <p className="mt-1 text-sm text-text-secondary">
          Copy each block below in order and paste into Google Ads Editor →
          File → Bulk edit → Make multiple changes (or Tools → Make multiple
          changes). All entities import as <strong>Paused</strong> so you
          can review before posting.
        </p>
      </header>

      <ol className="mt-4 space-y-4 text-sm">
        <Step
          n={1}
          title="Campaign"
          help={
            <>
              Creates one Search campaign with the right networks (search
              only — no Display, no Search Partners), locations, language,
              and Manual CPC bidding. Daily budget $5; you can raise after
              the first day of data.
            </>
          }
          tsv={toTsv(campaignRows)}
        />
        <Step
          n={2}
          title="Ad groups"
          help={<>One ad group per brief, same max-CPC as the campaign default.</>}
          tsv={toTsv(adGroupRows)}
        />
        <Step
          n={3}
          title={`Keywords (${keywordRows.length - 1} total, phrase match)`}
          help={
            <>
              All phrase-match by default — keeps Google from broad-matching
              to "free tennis live stream" type queries. After import, add
              campaign-level negatives:{" "}
              <code className="rounded bg-ink-800 px-1 text-text-primary">
                free, live stream, streaming, watch online, download
              </code>
              .
            </>
          }
          tsv={toTsv(keywordRows)}
        />
        <Step
          n={4}
          title={`Responsive Search Ads (${briefs.length} total)`}
          help={
            <>
              Each ad goes to the brief's UTM-tagged Final URL — clicks will
              show up in PostHog under{" "}
              <code className="rounded bg-ink-800 px-1 text-text-primary">
                $initial_utm_campaign
              </code>
              .
            </>
          }
          tsv={toTsv(adRows)}
        />
        <li className="rounded-md border border-ink-700 bg-ink-900 px-4 py-3 text-xs">
          <strong className="text-text-secondary">Final step:</strong>{" "}
          In Google Ads Editor, review the staged changes (Pending changes
          panel), confirm everything looks right, then click{" "}
          <strong>Post</strong>. Campaigns will go live in Paused state on
          Google's side — flip them to Enabled when you're ready to spend.
          Default end date is {fmtDate(endDate)} (14 days from launch).
        </li>
      </ol>
    </section>
  );
}

function Step({
  n,
  title,
  help,
  tsv,
}: {
  n: number;
  title: string;
  help: React.ReactNode;
  tsv: string;
}) {
  const [copied, setCopied] = useState(false);
  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(tsv);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard rejected; user can select-and-copy from the textarea below */
    }
  };
  return (
    <li className="rounded-md border border-ink-700 bg-ink-900 px-4 py-3">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-sm font-semibold">
          <span className="mr-2 inline-flex h-5 w-5 items-center justify-center rounded-full bg-accent text-[10px] font-bold text-white">
            {n}
          </span>
          {title}
        </h3>
        <button
          onClick={onCopy}
          className="rounded-full border border-ink-700 px-3 py-1 text-[11px] font-medium uppercase tracking-wider text-text-secondary hover:border-accent hover:text-accent"
        >
          {copied ? "Copied" : "Copy block"}
        </button>
      </div>
      <p className="mt-1 text-xs text-text-secondary">{help}</p>
      <textarea
        readOnly
        value={tsv}
        rows={4}
        className="mt-2 w-full overflow-auto rounded border border-ink-700 bg-ink-950 px-2 py-1 font-mono text-[10px] text-text-secondary"
      />
    </li>
  );
}

/**
 * Serialise a 2-D array as TSV. We quote fields containing tabs or
 * newlines (rare in our data) and pass everything else through verbatim
 * — Google Ads Editor reads quoted-on-demand and would mis-parse always-
 * quoted fields as if the quotes were literal.
 */
function toTsv(rows: string[][]): string {
  return rows
    .map((row) =>
      row
        .map((cell) => {
          const needsQuote = /[\t\n"]/.test(cell);
          if (!needsQuote) return cell;
          return `"${cell.replace(/"/g, '""')}"`;
        })
        .join("\t"),
    )
    .join("\n");
}
