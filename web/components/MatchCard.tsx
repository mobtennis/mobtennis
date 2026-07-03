import Link from "next/link";

import type { MatchSummary } from "@/lib/api";
import { formatMatchTime, formatRound, formatScore, formatSetScore } from "@/lib/format";
import { LiveDot, SuspendedDot } from "@/components/LiveDot";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PlayerHoverCard } from "@/components/PlayerHoverCard";

export function MatchCard({ match, dense = false }: { match: MatchSummary; dense?: boolean }) {
  const sets = formatScore(match.score);
  const isLive = match.status === "live";
  const isSuspended = match.status === "suspended";
  const finished = match.status === "finished";
  const round = formatRound(match.round);

  return (
    <Link
      href={`/matches/${match.id}`}
      className="group block overflow-hidden rounded-md border border-ink-700 bg-ink-900 px-3 py-2.5 transition hover:border-ink-600 hover:bg-ink-800"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-1 flex-col gap-1.5">
          {(() => {
            // Split "30 - 40" / "AD - 40" into per-player current-game points
            // so each player's row gets their own point as a final column.
            const [p1Game, p2Game] = (match.current_game ?? "").split(/\s*-\s*/, 2);
            const showGame = !dense && isLive;
            return (
              <>
                <PlayerRow
                  player={match.player1}
                  seed={match.player1_seed}
                  sets={sets.map((s) => s.split("-")[0])}
                  isServing={match.server_slot === 1}
                  isWinner={finished && match.winner_slot === 1}
                  isLoser={finished && match.winner_slot === 2}
                  gamePoints={showGame ? p1Game : null}
                />
                <PlayerRow
                  player={match.player2}
                  seed={match.player2_seed}
                  sets={sets.map((s) => s.split("-")[1] ?? "")}
                  isServing={match.server_slot === 2}
                  isWinner={finished && match.winner_slot === 2}
                  isLoser={finished && match.winner_slot === 1}
                  gamePoints={showGame ? p2Game : null}
                />
              </>
            );
          })()}
        </div>

        <div className="flex shrink-0 flex-col items-end gap-0.5 text-right">
          {isLive ? (
            <LiveDot />
          ) : isSuspended ? (
            <SuspendedDot />
          ) : !finished ? (
            // Finished matches show no status label — the score makes it obvious.
            // Scheduled matches show a relative-date + time stamp so users can
            // tell "tonight" from "Wednesday" at a glance. Empty when api-tennis
            // hasn't published the time yet (NULL scheduled_at).
            <span className="text-xs tnum text-text-secondary">
              {formatMatchTime(match.scheduled_at) || "TBD"}
            </span>
          ) : null}
          {/* Tour pill — sits between status and round labels in the
              meta column. Decorative only; the surrounding <Link>
              handles the click. */}
          {match.tournament_tour && <TourPill tour={match.tournament_tour} />}
          {round && (
            <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">{round}</span>
          )}
        </div>
      </div>
    </Link>
  );
}

function PlayerRow({
  player,
  seed,
  sets,
  isServing,
  isWinner = false,
  isLoser = false,
  gamePoints = null,
}: {
  player: MatchSummary["player1"];
  seed?: number | null;
  sets: string[];
  isServing: boolean;
  isWinner?: boolean;
  isLoser?: boolean;
  gamePoints?: string | null;
}) {
  if (!player) {
    return <div className="text-text-muted">TBD</div>;
  }
  return (
    <div className={`flex items-center gap-2 ${isLoser ? "opacity-50" : ""}`}>
      <PlayerAvatar name={player.full_name} imageUrl={player.image_url} countryCode={player.country_code} />
      <span className={`min-w-0 flex-1 truncate text-sm ${isWinner ? "font-bold text-text-primary" : "font-medium"}`}>
        {isWinner && <WinnerCheck />}
        {seed != null && (
          <span className="mr-1 text-[11px] font-semibold tnum text-text-muted">
            [{seed}]
          </span>
        )}
        <PlayerHoverCard slug={player.slug}>{player.full_name}</PlayerHoverCard>
        {isServing && (
          <span className="ml-1.5 inline-block h-1.5 w-1.5 rounded-full bg-accent align-middle" aria-label="serving" />
        )}
      </span>
      <span className="flex shrink-0 items-center gap-1.5">
        {sets.map((s, i) => (
          <span
            key={i}
            className={`tnum w-5 text-right text-sm tabular-nums ${
              isWinner ? "font-bold text-text-primary" : "font-semibold"
            }`}
          >
            {formatSetScore(s || "")}
          </span>
        ))}
        {gamePoints !== null && gamePoints !== "" && (
          <>
            <span className="h-4 w-px bg-ink-700" aria-hidden />
            <span className="tnum w-7 text-right text-sm font-bold tabular-nums text-accent">
              {gamePoints.trim()}
            </span>
          </>
        )}
      </span>
    </div>
  );
}

/** Small ATP/WTA badge tucked between the two player rows.
 * Color uses tour-conventional broadcasting tones — sky for ATP,
 * violet for WTA — distinct without being gendered. */
function TourPill({ tour }: { tour: string }) {
  const isAtp = tour.toLowerCase() === "atp";
  const cls = isAtp
    ? "bg-sky-100 text-sky-800 border-sky-200"
    : "bg-violet-100 text-violet-800 border-violet-200";
  return (
    <span
      className={`inline-flex h-[14px] items-center rounded-full border px-1.5 text-[8px] font-bold uppercase tracking-wider ${cls}`}
    >
      {tour.toUpperCase()}
    </span>
  );
}

function WinnerCheck() {
  return (
    <span className="mr-1 inline-flex h-3.5 w-3.5 items-center justify-center rounded-full bg-accent align-middle text-white">
      <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
        <path d="M5 12l5 5L20 7" />
      </svg>
    </span>
  );
}
