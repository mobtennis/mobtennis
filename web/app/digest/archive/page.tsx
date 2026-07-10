import Link from "next/link";

import { api, type DigestSummary } from "@/lib/api";
import { SectionHeader } from "@/components/SectionHeader";

export const revalidate = 600;

export const metadata = {
  title: "Digest archive",
  description:
    "Every weekly ATP & WTA recap from Mob Tennis — finals, upsets, and storylines, week by week.",
};

const PAGE_SIZE = 20;

function label(weekStart: string): string {
  return new Date(`${weekStart}T00:00:00Z`).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

export default async function DigestArchivePage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string }>;
}) {
  const { page: pageParam } = await searchParams;
  const page = Math.max(1, Number.parseInt(pageParam ?? "1", 10) || 1);
  const offset = (page - 1) * PAGE_SIZE;

  // Fetch one extra to detect a next page without a count query.
  const rows = await api<DigestSummary[]>(
    `/api/digests?limit=${PAGE_SIZE + 1}&offset=${offset}`,
    { revalidate: 600 },
  ).catch(() => [] as DigestSummary[]);

  const hasNext = rows.length > PAGE_SIZE;
  const items = rows.slice(0, PAGE_SIZE);
  const hasPrev = page > 1;

  return (
    <div className="space-y-6">
      <header>
        <Link
          href="/digest"
          className="text-xs font-medium text-accent hover:text-accent-dim"
        >
          ← Latest recap
        </Link>
        <h1 className="mt-2 text-2xl font-bold tracking-tight text-text-primary">
          Digest archive
        </h1>
        <p className="mt-1 text-sm text-text-muted">
          Every weekly recap, newest first.
        </p>
      </header>

      {items.length === 0 ? (
        <p className="rounded-lg border border-ink-700 bg-ink-900 p-5 text-sm text-text-muted">
          Nothing here — try an earlier page.
        </p>
      ) : (
        <ul className="divide-y divide-ink-700 overflow-hidden rounded-lg border border-ink-700 bg-ink-900">
          {items.map((d) => (
            <li key={d.week_start}>
              <Link
                href={`/digest/${d.week_start}`}
                className="flex items-center gap-3 px-3 py-3 text-sm hover:bg-ink-800"
              >
                <span className="w-28 shrink-0 whitespace-nowrap text-[11px] uppercase tracking-wider text-text-muted">
                  {label(d.week_start)}
                </span>
                <span className="line-clamp-1 flex-1 font-medium text-text-primary">
                  {d.headline}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}

      <nav className="flex items-center justify-between gap-3">
        {hasPrev ? (
          <Link
            href={`/digest/archive?page=${page - 1}`}
            className="rounded-md border border-ink-700 bg-ink-900 px-3 py-2 text-xs font-medium hover:border-ink-600"
          >
            ← Newer
          </Link>
        ) : (
          <span />
        )}
        <span className="text-[11px] uppercase tracking-wider text-text-muted">
          Page {page}
        </span>
        {hasNext ? (
          <Link
            href={`/digest/archive?page=${page + 1}`}
            className="rounded-md border border-ink-700 bg-ink-900 px-3 py-2 text-xs font-medium hover:border-ink-600"
          >
            Older →
          </Link>
        ) : (
          <span />
        )}
      </nav>
    </div>
  );
}
