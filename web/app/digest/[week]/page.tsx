import Link from "next/link";
import { notFound } from "next/navigation";

import { api, type DigestDetail, type DigestSummary } from "@/lib/api";
import { DigestBody, stripMarkdownLinks } from "@/components/DigestBody";
import { SectionHeader } from "@/components/SectionHeader";
import { TrackOnMount } from "@/components/TrackOnMount";
import { EVENTS } from "@/lib/analytics";

// Disable Vercel's page-level ISR. Digest detail pages get edited
// mid-day (re-force after a data fix, sources-block bug, prompt
// iteration), and a 24h ISR window stranded users on the stale HTML
// for the rest of the day. Backend has source_json cached so this
// stays cheap; the per-fetch revalidate=0 below pairs with it.
export const revalidate = 0;

// How many past recaps to show inline on an article before deferring to
// the paginated /digest/archive page.
const ARCHIVE_PREVIEW = 8;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ week: string }>;
}) {
  const { week } = await params;
  const digest = await api<DigestDetail>(`/api/digests/${week}`, {
    revalidate: 0,
  }).catch(() => null);
  if (!digest) return { title: "Weekly digest" };
  return {
    title: digest.headline,
    description: stripMarkdownLinks(digest.body_md)
      .split(/(?<=\.)\s+/, 2)
      .join(" ")
      .slice(0, 200),
  };
}

export default async function DigestWeekPage({
  params,
}: {
  params: Promise<{ week: string }>;
}) {
  const { week } = await params;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(week)) notFound();

  const [digest, archive] = await Promise.all([
    // revalidate=0: bypass the Next.js fetch cache. Digests get edited
    // mid-day (force re-runs after a fact correction or prompt tweak)
    // and a long-lived cache stranded users on the old version for 24h.
    // Backend keeps response shape small and source_json parsing cheap.
    api<DigestDetail>(`/api/digests/${week}`, { revalidate: 0 }).catch(() => null),
    // 100 is enough for any reasonable archive view + neighbour lookup.
    api<DigestSummary[]>(`/api/digests?limit=100`, { revalidate: 600 }).catch(
      () => [] as DigestSummary[],
    ),
  ]);
  if (!digest) notFound();

  // Archive is newest-first. Find this week's index to surface prev/next.
  const idx = archive.findIndex((d) => d.week_start === week);
  const newer = idx > 0 ? archive[idx - 1] : null;
  const older = idx >= 0 && idx + 1 < archive.length ? archive[idx + 1] : null;

  return (
    <div className="space-y-6">
      <TrackOnMount
        event={EVENTS.digestOpened}
        properties={{ week_start: digest.week_start }}
      />

      <header className="rounded-lg border border-ink-700 bg-ink-900 p-5 shadow-card">
        <div className="text-[10px] font-bold uppercase tracking-wider text-accent">
          {coverageEyebrow(digest)}
        </div>
        <div className="mt-1 text-xs uppercase tracking-wider text-text-muted">
          {coverageLabel(digest)}
        </div>
        <h1 className="mt-3 text-2xl font-bold tracking-tight text-text-primary">
          {digest.headline}
        </h1>
        <Link
          href="/about"
          className="mt-3 inline-block text-xs text-text-muted underline decoration-dotted underline-offset-4 hover:text-text-secondary"
        >
          By the Mob Tennis team
        </Link>
      </header>

      <article className="rounded-lg border border-ink-700 bg-ink-900 p-5 shadow-card">
        {/* DigestBody parses inline markdown links of the form
            `[text](url)` from the body. Two link kinds coexist:
            internal slugs (`/players/...`, `/tournaments/...`,
            `/h2h/...`) and external news citations (`https://...`),
            both produced by the LLM under the editorial-digest
            prompt and validated by the backend sanitizer. No other
            markdown is supported — the body is one flowing
            paragraph. */}
        <DigestBody body={digest.body_md} />
      </article>

      <nav className="flex items-center justify-between gap-3">
        {older ? (
          <Link
            href={`/digest/${older.week_start}`}
            className="flex-1 rounded-md border border-ink-700 bg-ink-900 px-3 py-2 text-xs hover:border-ink-600"
          >
            <div className="text-text-muted">← Previous week</div>
            <div className="mt-0.5 line-clamp-1 font-medium text-text-primary">
              {older.headline}
            </div>
          </Link>
        ) : (
          <span className="flex-1" />
        )}
        {newer ? (
          <Link
            href={`/digest/${newer.week_start}`}
            className="flex-1 rounded-md border border-ink-700 bg-ink-900 px-3 py-2 text-right text-xs hover:border-ink-600"
          >
            <div className="text-text-muted">Next week →</div>
            <div className="mt-0.5 line-clamp-1 font-medium text-text-primary">
              {newer.headline}
            </div>
          </Link>
        ) : (
          <span className="flex-1" />
        )}
      </nav>

      {archive.length > 2 && (
        <section>
          <SectionHeader title="Archive" subtitle="Past weekly recaps" />
          {/* Only the most recent handful inline — the full list grows
              every week and buried the article. The rest live on the
              paginated archive page. */}
          <ul className="mt-2 divide-y divide-ink-700 overflow-hidden rounded-lg border border-ink-700 bg-ink-900">
            {archive.slice(0, ARCHIVE_PREVIEW).map((d) => (
              <li key={d.week_start}>
                <Link
                  href={`/digest/${d.week_start}`}
                  className={`flex items-center gap-3 px-3 py-3 text-sm hover:bg-ink-800 ${
                    d.week_start === week ? "bg-ink-800" : ""
                  }`}
                >
                  <span className="w-32 shrink-0 whitespace-nowrap text-[11px] uppercase tracking-wider text-text-muted">
                    {archiveLabel(d.week_start)}
                  </span>
                  <span className="line-clamp-1 flex-1 font-medium text-text-primary">
                    {d.headline}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
          {archive.length > ARCHIVE_PREVIEW && (
            <Link
              href="/digest/archive"
              className="mt-3 inline-block text-xs font-semibold text-accent hover:text-accent-dim"
            >
              View all recaps →
            </Link>
          )}
        </section>
      )}
    </div>
  );
}

// Day-precision (UTC) so we can ask "did this digest cover one
// calendar day or more?" without timezone surprises.
function _dayStart(d: Date): number {
  return Math.floor(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()) / 86_400_000);
}

function _fmtDay(d: Date): string {
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
}

/**
 * Eyebrow text — adapts to the digest's actual coverage window.
 * Earlier this was hard-coded "This week in tennis", which read as
 * a falsehood for the daily-during-Slams digests that only span
 * ~20 hours.
 *
 * Bucketed by elapsed hours, not by calendar-day diff, so a digest
 * covering "yesterday evening → this morning" reads as a single
 * recap (~20h) rather than "the last few days" (which the day-diff
 * would say because midnight passed).
 *
 *   ≤ 30 h  → "Tennis recap"           (single daily run)
 *   ≤ 96 h  → "The last few days in tennis"
 *   > 96 h  → "This week in tennis"    (Monday cron / catch-up)
 *   unknown → "This week in tennis"    (legacy backfilled rows)
 */
function coverageEyebrow(d: { period_start: string | null; period_end: string | null }): string {
  if (!d.period_start || !d.period_end) return "This week in tennis";
  const hours =
    (new Date(d.period_end).getTime() - new Date(d.period_start).getTime()) / 3_600_000;
  if (hours <= 30) return "Tennis recap";
  if (hours <= 96) return "The last few days in tennis";
  return "This week in tennis";
}

/**
 * Subtitle range. Single-day windows show one date; multi-day windows
 * show a range; legacy rows without explicit periods fall back to
 * the anchor date alone (no fake week-ahead extrapolation).
 */
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

/**
 * Archive-row label. The list endpoint only returns `week_start`
 * (no period fields), so we just show the anchor date — accurate
 * for daily digests, and for older weekly rows it's the start of
 * the covered week which is the best signal we have here.
 */
function archiveLabel(weekStart: string): string {
  return _fmtDay(new Date(`${weekStart}T00:00:00Z`));
}
