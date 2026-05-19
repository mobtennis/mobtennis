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
          This week in tennis
        </h2>
        <span className="text-[10px] uppercase tracking-wider text-text-muted">
          {formatWeekLabel(digest.week_start)}
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

function formatWeekLabel(weekStart: string): string {
  const start = new Date(`${weekStart}T00:00:00Z`);
  const end = new Date(start);
  end.setUTCDate(end.getUTCDate() + 6);
  const fmt = (d: Date) =>
    d.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
  return `${fmt(start)} – ${fmt(end)}`;
}
