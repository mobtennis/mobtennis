import Link from "next/link";
import { notFound } from "next/navigation";

import { api, type DigestDetail, type DigestSummary } from "@/lib/api";
import { SectionHeader } from "@/components/SectionHeader";
import { TrackOnMount } from "@/components/TrackOnMount";
import { EVENTS } from "@/lib/analytics";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ week: string }>;
}) {
  const { week } = await params;
  const digest = await api<DigestDetail>(`/api/digests/${week}`, {
    revalidate: 86400,
  }).catch(() => null);
  if (!digest) return { title: "Weekly digest" };
  return {
    title: digest.headline,
    description: digest.body_md.split(/(?<=\.)\s+/, 2).join(" ").slice(0, 200),
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
    api<DigestDetail>(`/api/digests/${week}`, { revalidate: 86400 }).catch(() => null),
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
          This week in tennis
        </div>
        <div className="mt-1 text-xs uppercase tracking-wider text-text-muted">
          {formatWeekLabel(digest.week_start)}
        </div>
        <h1 className="mt-3 text-2xl font-bold tracking-tight text-text-primary">
          {digest.headline}
        </h1>
        <div className="mt-3 text-xs text-text-muted">
          By the Mobtennis team
        </div>
      </header>

      <article className="rounded-lg border border-ink-700 bg-ink-900 p-5 shadow-card">
        {/* Body is a single paragraph by design — render as such, no
            markdown parser needed. Whitespace preserved in case the
            model emits soft line breaks anyway. */}
        <p className="whitespace-pre-line text-[15px] leading-7 text-text-secondary">
          {digest.body_md}
        </p>
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
          <ul className="mt-2 divide-y divide-ink-700 overflow-hidden rounded-lg border border-ink-700 bg-ink-900">
            {archive.map((d) => (
              <li key={d.week_start}>
                <Link
                  href={`/digest/${d.week_start}`}
                  className={`flex items-center gap-3 px-3 py-3 text-sm hover:bg-ink-800 ${
                    d.week_start === week ? "bg-ink-800" : ""
                  }`}
                >
                  <span className="w-24 shrink-0 text-[11px] uppercase tracking-wider text-text-muted">
                    {formatWeekLabel(d.week_start)}
                  </span>
                  <span className="line-clamp-1 flex-1 font-medium text-text-primary">
                    {d.headline}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function formatWeekLabel(weekStart: string): string {
  const start = new Date(`${weekStart}T00:00:00Z`);
  const end = new Date(start);
  end.setUTCDate(end.getUTCDate() + 6);
  const fmt = (d: Date) =>
    d.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
  return `${fmt(start)} – ${fmt(end)}`;
}
