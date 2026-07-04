import Link from "next/link";
import { notFound } from "next/navigation";

import { api, type MatchDetail, type VideoItemSummary } from "@/lib/api";
import { AdSlot } from "@/components/AdSlot";
// LiveMatchListener removed — MatchDetailLiveHeader owns its own SSE
// subscription via the shared live-stream hook.
import { MatchStatsPanel } from "@/components/MatchStatsPanel";
import { PlayerHoverCard } from "@/components/PlayerHoverCard";
import { TrackOnMount } from "@/components/TrackOnMount";
import { VideoCard } from "@/components/VideoCard";
import { EVENTS } from "@/lib/analytics";
import { MatchDetailLiveHeader } from "@/components/MatchDetailLiveHeader";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  // Same revalidate as the page body fetch below so Next.js dedupes the
  // two into a single backend call within a request.
  const match = await api<MatchDetail>(`/api/matches/${id}`, { revalidate: 10 }).catch(
    () => null,
  );
  if (!match) return { title: `Match ${id}` };

  const p1 = match.player1?.full_name;
  const p2 = match.player2?.full_name;
  const event = match.tournament_name
    ? `${match.tournament_name}${match.tournament_year ? ` ${match.tournament_year}` : ""}`
    : null;
  if (p1 && p2) {
    return { title: event ? `${p1} vs ${p2} — ${event}` : `${p1} vs ${p2}` };
  }
  return { title: event ?? `Match ${id}` };
}

export default async function MatchPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  // revalidate: 0 — live-updating page. Live status/score flows in
  // via the shared SSE stream that MatchDetailLiveHeader subscribes
  // to; the server render only needs to hand off the *initial*
  // snapshot for SEO + first paint. Any Data-Cache TTL here would
  // just mean stale first-paint after a soft-refresh.
  const match = await api<MatchDetail>(`/api/matches/${id}`, { revalidate: 0 }).catch(() => null);
  if (!match) notFound();

  // Fuzzy-matched highlights for this specific Match row. Cheap query
  // (indexed match_id) and most matches will have 0–2 hits.
  const highlights = await api<VideoItemSummary[]>(
    `/api/videos?match_id=${id}&limit=4`,
    { revalidate: 120 },
  ).catch(() => [] as VideoItemSummary[]);

  return (
    <div className="space-y-4">
      <TrackOnMount
        event={EVENTS.matchOpened}
        properties={{
          match_id: match.id,
          status: match.status,
          tournament_slug: match.tournament_slug,
          tournament_tour: match.tournament_tour,
          tournament_category: match.tournament_category,
          is_doubles: match.is_doubles,
        }}
      />

      <Link
        href={`/tournaments/${match.tournament_tour ?? "atp"}/${match.tournament_slug}`}
        className="text-xs font-medium text-accent hover:text-accent-dim"
      >
        ← {match.tournament_name}
      </Link>

      <MatchDetailLiveHeader initial={match} />

      {match.blurb && match.blurb.paragraph && (
        <section
          className="rounded-lg border border-ink-700 bg-ink-900 p-4 shadow-card"
          aria-label={match.blurb.kind === "recap" ? "Match recap" : "Match preview"}
        >
          <h2 className="text-[10px] font-bold uppercase tracking-wider text-text-muted">
            {match.blurb.kind === "recap" ? "Recap" : "Preview"}
          </h2>
          <p className="mt-2 text-sm leading-6 text-text-secondary">
            {match.blurb.paragraph}
          </p>
        </section>
      )}

      {match.stats && (
        <MatchStatsPanel
          stats={match.stats}
          player1={match.player1}
          player2={match.player2}
        />
      )}

      <AdSlot slot="match-mid" />

      {match.player1 && match.player2 && (
        <Link
          href={`/h2h/${match.player1.slug}-vs-${match.player2.slug}`}
          className="block rounded-md border border-ink-700 bg-ink-900 px-3 py-3 text-center text-sm font-medium hover:border-ink-600"
        >
          Head-to-head:{" "}
          <PlayerHoverCard slug={match.player1.slug}>{match.player1.full_name}</PlayerHoverCard>
          {" vs "}
          <PlayerHoverCard slug={match.player2.slug}>{match.player2.full_name}</PlayerHoverCard>
        </Link>
      )}

      {highlights.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-text-muted">
            Highlights
          </h2>
          <div className="space-y-2">
            {highlights.map((v) => (
              <VideoCard key={v.id} video={v} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

// PlayerLine moved into MatchDetailLiveHeader.
