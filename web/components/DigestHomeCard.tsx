import Link from "next/link";

import { stripMarkdownLinks } from "@/components/DigestBody";
import { api, type DigestDetail } from "@/lib/api";

/**
 * Home-page teaser linking to the full weekly digest. Fetches the
 * latest row and renders headline + lead sentence. Renders nothing
 * when no digest has been generated yet (fresh deploy, no
 * ANTHROPIC_API_KEY, etc.) — keeps the home page from showing a
 * dead section.
 */
export async function DigestHomeCard() {
  const digest = await api<DigestDetail>("/api/digests/latest", {
    revalidate: 600,
  }).catch(() => null);
  if (!digest) return null;

  // Two-line preview from the body. Splitting on ". " is good enough —
  // the body is a single paragraph so we just need the first beat.
  // Markdown links are flattened to plain text because the whole card
  // is already a single Link to /digest/[week]; nested <a>s would
  // produce invalid HTML and clobber the click target.
  const lead = stripMarkdownLinks(digest.body_md)
    .split(/(?<=\.)\s+/, 2)
    .join(" ");

  return (
    <section className="rounded-lg border border-ink-700 bg-ink-900 p-4 shadow-card">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-[10px] font-bold uppercase tracking-wider text-accent">
          {coverageEyebrow(digest)}
        </h2>
        <span className="text-[10px] uppercase tracking-wider text-text-muted">
          {coverageLabel(digest)}
        </span>
      </div>
      <Link href="/digest" className="mt-2 block hover:opacity-80">
        <h3 className="text-base font-semibold tracking-tight text-text-primary">
          {digest.headline}
        </h3>
        <p className="mt-1 line-clamp-3 text-sm leading-6 text-text-secondary">
          {lead}
        </p>
        <span className="mt-2 inline-block text-xs font-medium text-accent">
          Read the full recap →
        </span>
      </Link>
    </section>
  );
}

// Coverage label helpers — accurate to the digest's actual period.
// Earlier this card added 6 days to week_start to produce a fake
// "May 30 – Jun 5" range even for 20-hour daily digests. See the
// same pair of helpers in app/digest/[week]/page.tsx for the full
// rationale; mirrored here so the home card matches.

function _dayStart(d: Date): number {
  return Math.floor(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()) / 86_400_000);
}

function _fmtDay(d: Date): string {
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
}

function coverageEyebrow(d: { period_start: string | null; period_end: string | null }): string {
  if (!d.period_start || !d.period_end) return "This week in tennis";
  const hours =
    (new Date(d.period_end).getTime() - new Date(d.period_start).getTime()) / 3_600_000;
  if (hours <= 30) return "Tennis recap";
  if (hours <= 96) return "The last few days in tennis";
  return "This week in tennis";
}

function coverageLabel(d: {
  period_start: string | null;
  period_end: string | null;
  week_start: string;
}): string {
  if (!d.period_start || !d.period_end) {
    return _fmtDay(new Date(`${d.week_start}T00:00:00Z`));
  }
  const s = new Date(d.period_start);
  const e = new Date(d.period_end);
  if (_dayStart(s) === _dayStart(e)) return _fmtDay(e);
  return `${_fmtDay(s)} – ${_fmtDay(e)}`;
}
