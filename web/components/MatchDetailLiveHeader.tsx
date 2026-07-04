"use client";

import Link from "next/link";
import { useMemo } from "react";

import type { MatchDetail, MatchSummary } from "@/lib/api";
import { formatScore, formatSetScore } from "@/lib/format";
import { LiveDot, SuspendedDot } from "@/components/LiveDot";
import { LocalTime } from "@/components/LocalTime";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PlayerHoverCard } from "@/components/PlayerHoverCard";
import { useLiveMatch } from "@/lib/live-stream";

/**
 * Live-reactive score + status header for the match detail page.
 * Renders identical output to the previous inline server-rendered
 * header, but subscribes to the shared SSE stream so score, sets,
 * current game, serving, and status update sub-second without a
 * router refresh.
 */

export function MatchDetailLiveHeader({ initial }: { initial: MatchDetail }) {
  const live = useLiveMatch(initial.id);
  // MatchSummary is a proper subset of MatchDetail; merging just
  // overlays the fields the SSE payload carries.
  const match = useMemo<MatchDetail>(() => (
    live ? mergeSummary(initial, live) : initial
  ), [initial, live]);

  const sets = formatScore(match.score);
  const isLive = match.status === "live";
  const isSuspended = match.status === "suspended";
  const showGameScore = isLive;
  const [p1Game, p2Game] = (match.current_game ?? "").split(/\s*-\s*/, 2);

  return (
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

      {!isLive && !isSuspended && match.scheduled_at && (
        <div className="mt-3 text-center text-xs text-text-muted">
          <LocalTime iso={match.scheduled_at} variant="time" />
        </div>
      )}
      {isSuspended && (
        <div className="mt-3 text-center text-xs italic text-amber-400/80">
          Play suspended — score frozen until play resumes.
        </div>
      )}
    </header>
  );
}


function mergeSummary(base: MatchDetail, summary: MatchSummary): MatchDetail {
  return { ...base, ...summary };
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
          <PlayerHoverCard slug={player.slug}>{player.full_name}</PlayerHoverCard>
        </span>
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
