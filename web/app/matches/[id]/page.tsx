import Link from "next/link";
import { notFound } from "next/navigation";

import { api, type MatchDetail, type VideoItemSummary } from "@/lib/api";
import { AdSlot } from "@/components/AdSlot";
import { LiveDot, SuspendedDot } from "@/components/LiveDot";
import { LiveMatchListener } from "@/components/LiveMatchListener";
import { MatchStatsPanel } from "@/components/MatchStatsPanel";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { TrackOnMount } from "@/components/TrackOnMount";
import { VideoCard } from "@/components/VideoCard";
import { EVENTS } from "@/lib/analytics";
import { formatScore, formatSetScore, formatTime } from "@/lib/format";

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
  const match = await api<MatchDetail>(`/api/matches/${id}`, { revalidate: 10 }).catch(() => null);
  if (!match) notFound();

  // Fuzzy-matched highlights for this specific Match row. Cheap query
  // (indexed match_id) and most matches will have 0–2 hits.
  const highlights = await api<VideoItemSummary[]>(
    `/api/videos?match_id=${id}&limit=4`,
    { revalidate: 120 },
  ).catch(() => [] as VideoItemSummary[]);

  const sets = formatScore(match.score);
  const isLive = match.status === "live";
  const isSuspended = match.status === "suspended";
  const showGameScore = isLive; // suspended → no current-game pip; play is paused

  return (
    <div className="space-y-4">
      {/* Keep the live listener wired for suspended matches too — they
          flip back to live without warning when play resumes. */}
      <LiveMatchListener matchId={match.id} enabled={isLive || isSuspended} />
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

      <header className="rounded-lg border border-ink-700 bg-ink-900 p-4 shadow-card">
        <div className="flex items-center justify-between text-xs text-text-muted">
          <span>{match.round && `Round: ${match.round}`}</span>
          {isLive ? (
            <LiveDot />
          ) : isSuspended ? (
            <SuspendedDot />
          ) : (
            <span className="uppercase tracking-wider">{match.status}</span>
          )}
        </div>

        {(() => {
          // Split "30 - 40" / "AD - 40" into per-player current-game points
          // so we can render each as the last column instead of a banner.
          const [p1Game, p2Game] = (match.current_game ?? "").split(/\s*-\s*/, 2);
          return (
            <div className="mt-3 grid grid-cols-[1fr_auto] items-center gap-4">
              <PlayerLine
                player={match.player1}
                seed={match.player1_seed}
                sets={sets.map((s) => s.split("-")[0])}
                serving={match.server_slot === 1}
                isWinner={match.status === "finished" && match.winner_slot === 1}
                isLoser={match.status === "finished" && match.winner_slot === 2}
                gamePoints={showGameScore ? p1Game : null}
              />
              <span className="text-[10px] text-text-muted uppercase tracking-wider">vs</span>
              <PlayerLine
                player={match.player2}
                seed={match.player2_seed}
                sets={sets.map((s) => s.split("-")[1] ?? "")}
                serving={match.server_slot === 2}
                isWinner={match.status === "finished" && match.winner_slot === 2}
                isLoser={match.status === "finished" && match.winner_slot === 1}
                gamePoints={showGameScore ? p2Game : null}
              />
            </div>
          );
        })()}

        {!isLive && !isSuspended && match.scheduled_at && (
          <div className="mt-3 text-center text-xs text-text-muted">
            {formatTime(match.scheduled_at)}
          </div>
        )}
        {isSuspended && (
          <div className="mt-3 text-center text-xs italic text-amber-400/80">
            Play suspended — score frozen until play resumes.
          </div>
        )}
      </header>

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
          Head-to-head: {match.player1.full_name} vs {match.player2.full_name}
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

function PlayerLine({
  player,
  seed,
  sets,
  serving,
  isWinner = false,
  isLoser = false,
  gamePoints = null,
}: {
  player: MatchDetail["player1"];
  seed?: number | null;
  sets: string[];
  serving: boolean;
  isWinner?: boolean;
  isLoser?: boolean;
  /** In-game point score (15/30/40/AD) — rendered as the last column when
   * the match is live. Null suppresses the column. */
  gamePoints?: string | null;
}) {
  if (!player) return <div className="text-text-muted">TBD</div>;
  return (
    <div className={`col-span-2 flex items-center gap-3 ${isLoser ? "opacity-50" : ""}`}>
      <PlayerAvatar name={player.full_name} imageUrl={player.image_url} countryCode={player.country_code} size="md" />
      <Link
        href={`/players/${player.slug}`}
        className="flex min-w-0 flex-1 items-center gap-2 hover:text-accent"
      >
        {isWinner && (
          <span className="inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-accent text-white">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M5 12l5 5L20 7" />
            </svg>
          </span>
        )}
        <span className={`min-w-0 truncate text-base ${isWinner ? "font-bold" : "font-semibold"}`}>
          {seed != null && (
            <span className="mr-1.5 text-xs font-normal text-text-muted tabular-nums">[{seed}]</span>
          )}
          {player.full_name}
        </span>
        {/* `shrink-0` so the dot survives a long name being truncated. */}
        {serving && (
          <span className="h-2 w-2 shrink-0 rounded-full bg-accent" aria-label="serving" />
        )}
      </Link>
      <span className="flex shrink-0 items-center gap-2">
        {sets.map((s, i) => (
          <span key={i} className="tnum w-6 text-right text-lg font-bold tabular-nums">{formatSetScore(s || "")}</span>
        ))}
        {gamePoints !== null && gamePoints !== "" && (
          <>
            <span className="h-5 w-px bg-ink-700" aria-hidden />
            <span className="tnum w-8 text-right text-lg font-bold tabular-nums text-accent">
              {gamePoints.trim()}
            </span>
          </>
        )}
      </span>
    </div>
  );
}
