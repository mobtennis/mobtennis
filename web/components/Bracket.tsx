"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import type { MatchSummary, PlayerSummary } from "@/lib/api";
import { formatRound, formatSetScore, roundDepth } from "@/lib/format";

const MAIN_DRAW_MIN_DEPTH = 40;

// Maps each round to the round immediately below it (which contains
// its two feeder matches). Used to look up who advanced from the top
// vs bottom of the previous column so we can show players in
// draw-position order — top feeder's winner on top of the cell, bottom
// feeder's winner on bottom — instead of "winner of this match always
// on top," which makes the lines visually cross when an upset happens.
const DEEPER_ROUND: Record<string, string> = {
  F: "SF", SF: "QF", QF: "R16", R16: "R32", R32: "R64", R64: "R128", R128: "R256",
};

type Props = {
  matches: MatchSummary[];
  drawSize?: number | null;
  /** When true (in-progress tournaments), pad each column with TBD/projected
   * cells up to the expected count. */
  padPlaceholders?: boolean;
};

export function Bracket({ matches, drawSize, padPlaceholders = false }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full rounded-md border border-ink-700 bg-ink-900 px-3 py-2.5 text-sm font-semibold text-text-primary transition hover:border-ink-600 hover:bg-ink-800"
      >
        {open ? "Hide bracket" : "Show bracket"}
      </button>
      {open && (
        <div className="mt-3">
          <BracketGrid matches={matches} drawSize={drawSize ?? null} padPlaceholders={padPlaceholders} />
        </div>
      )}
    </div>
  );
}

// ---- Cell model -----------------------------------------------------------

type Cell =
  | { kind: "match"; match: MatchSummary }
  | { kind: "projected"; p1: PlayerSummary | null; p2: PlayerSummary | null }
  | { kind: "tbd" };

type Column = {
  depth: number;
  label: string;
  cells: Cell[];
};

// ---- Helpers --------------------------------------------------------------

function expectedForRound(drawSize: number, depth: number): number {
  // F=100 (1), SF=90 (2), QF=80 (4), R16=70 (8), R32=60 (16), R64=50 (32), R128=40 (64)
  const stepsFromFinal = (100 - depth) / 10;
  if (stepsFromFinal < 0) return 0;
  return Math.min(2 ** stepsFromFinal, Math.floor(drawSize / 2));
}

function labelFromDepth(depth: number): string {
  return (
    {
      100: "F", 90: "SF", 80: "QF", 70: "R16", 60: "R32", 50: "R64", 40: "R128", 30: "R256",
    } as Record<number, string>
  )[depth] ?? "—";
}

function winnerOf(m: MatchSummary): PlayerSummary | null {
  if (m.status !== "finished") return null;
  if (m.winner_slot === 1) return m.player1;
  if (m.winner_slot === 2) return m.player2;
  return null;
}

// Sort key for matches without bracket_position. Used to fill cells
// sequentially for past tournaments where the Wikipedia scraper didn't
// run (Sackmann-ingested data has scores + seeds but no draw structure).
// api_tennis_id is roughly chronological so it produces a sensible
// row order within a round; falling back to id or scheduled_at when
// missing.
function positionalSort(a: MatchSummary, b: MatchSummary): number {
  const aId = a.api_tennis_id ? parseInt(a.api_tennis_id, 10) : NaN;
  const bId = b.api_tennis_id ? parseInt(b.api_tennis_id, 10) : NaN;
  if (!Number.isNaN(aId) && !Number.isNaN(bId)) return aId - bId;
  const at = a.scheduled_at ? new Date(a.scheduled_at).getTime() : 0;
  const bt = b.scheduled_at ? new Date(b.scheduled_at).getTime() : 0;
  if (at !== bt) return at - bt;
  return a.id - b.id;
}

// ---- Column construction --------------------------------------------------

function buildColumns(
  matches: MatchSummary[],
  drawSize: number | null,
  padPlaceholders: boolean,
): Column[] {
  // Singles main-draw only.
  const byDepth = new Map<number, MatchSummary[]>();
  for (const m of matches) {
    const d = roundDepth(m.round);
    if (d < MAIN_DRAW_MIN_DEPTH) continue;
    if (!byDepth.has(d)) byDepth.set(d, []);
    byDepth.get(d)!.push(m);
  }

  // Two placement strategies, picked based on what the data has:
  //   - "structured": at least one match has bracket_position (Wikipedia
  //     scraper has run). Place each match at its specified slot.
  //   - "positional": no match has bracket_position (Sackmann-only or
  //     api-tennis without Wikipedia). Sort by positionalSort and fill
  //     cells sequentially. Less precise but produces a sensible
  //     visual ordering for completed past tournaments.
  // Picking per-render rather than globally so a partly-scraped live
  // tournament still gets strict placement.
  const haveStructure = matches.some((m) => m.bracket_position !== null);

  const depths = new Set(byDepth.keys());
  if (padPlaceholders && depths.size > 0) {
    const minDepth = Math.min(...depths);
    for (let d = minDepth; d <= 100; d += 10) depths.add(d);
  }

  const cols: Column[] = [];
  let prevExpected = 0;
  for (const depth of [...depths].sort((a, b) => a - b)) {
    const ms = byDepth.get(depth) ?? [];

    let expected: number;
    if (drawSize) {
      expected = expectedForRound(drawSize, depth);
    } else if (prevExpected === 0) {
      const maxPos = Math.max(
        0,
        ms.length,
        ...ms.map((m) => (m.bracket_position ?? 0) + 1),
      );
      expected = Math.max(maxPos, 1);
    } else {
      expected = Math.max(1, Math.ceil(prevExpected / 2));
    }
    expected = Math.max(
      expected,
      ms.length,
      ...ms.map((m) => (m.bracket_position ?? 0) + 1),
    );

    const cells: Cell[] = Array.from({ length: expected }, () => ({ kind: "tbd" }));
    if (haveStructure) {
      // Strict: place at exact bracket_position. Slots without a real
      // match stay TBD (typically byes in early rounds).
      for (const m of ms) {
        const idx = m.bracket_position ?? -1;
        if (idx >= 0 && idx < cells.length) {
          cells[idx] = { kind: "match", match: m };
        }
      }
    } else {
      // Fallback: sort + sequential fill. For past Sackmann data this
      // gives a clean round-by-round bracket even though we can't
      // promise top-to-bottom draw order is perfect.
      const sorted = [...ms].sort(positionalSort);
      for (let i = 0; i < Math.min(sorted.length, cells.length); i++) {
        cells[i] = { kind: "match", match: sorted[i] };
      }
    }

    cols.push({
      depth,
      label: formatRound(ms[0]?.round ?? null) || labelFromDepth(depth),
      cells,
    });
    prevExpected = expected;
  }

  if (padPlaceholders) projectWinnersForward(cols);
  return cols;
}

// Walk every column; for each finished match at position N, propagate the
// winner into the next column at position floor(N/2), slot N % 2 (0 → p1,
// 1 → p2). Only fills TBD or partially-filled projected cells; never
// overrides real match data.
function projectWinnersForward(cols: Column[]): void {
  for (let ci = 0; ci < cols.length - 1; ci++) {
    const cur = cols[ci];
    const next = cols[ci + 1];
    for (let pos = 0; pos < cur.cells.length; pos++) {
      const cell = cur.cells[pos];
      if (cell.kind !== "match") continue;
      const winner = winnerOf(cell.match);
      if (!winner) continue;
      const nextPos = Math.floor(pos / 2);
      if (nextPos >= next.cells.length) continue;
      const target = next.cells[nextPos];
      if (target.kind === "match") continue;
      const isP1 = pos % 2 === 0;
      const existingP1 = target.kind === "projected" ? target.p1 : null;
      const existingP2 = target.kind === "projected" ? target.p2 : null;
      next.cells[nextPos] = {
        kind: "projected",
        p1: isP1 ? winner : existingP1,
        p2: isP1 ? existingP2 : winner,
      };
    }
  }
}

// ---- Render ---------------------------------------------------------------

export function BracketGrid({
  matches,
  drawSize,
  padPlaceholders,
}: {
  matches: MatchSummary[];
  drawSize: number | null;
  padPlaceholders: boolean;
}) {
  const cols = buildColumns(matches, drawSize, padPlaceholders);
  // Index by (round, bracket_position) so each cell can find its two
  // feeder matches in the deeper round in O(1).
  const feederIdx = useMemo(() => {
    const m = new Map<string, MatchSummary>();
    for (const x of matches) {
      if (x.bracket_position !== null && x.round) {
        m.set(`${x.round.toUpperCase()}|${x.bracket_position}`, x);
      }
    }
    return m;
  }, [matches]);
  if (cols.length === 0) return null;

  const hasProjections = cols.some((c) => c.cells.some((cell) => cell.kind === "projected"));

  return (
    <div className="overflow-x-auto">
      {/* items-stretch on the outer flex makes shorter columns fill the
          tallest column's height; justify-center inside each column then
          centers cells — F sits in the vertical middle of the canvas. */}
      <div className="flex min-w-max gap-2 pb-2">
        {cols.map((col) => (
          <div key={col.depth} className="flex w-52 shrink-0 flex-col">
            <div className="mb-2 text-center text-[10px] font-bold uppercase tracking-wider text-text-muted">
              {col.label}
              <span className="ml-1 text-text-muted/60">· {col.cells.length}</span>
            </div>
            <div className="flex flex-1 flex-col justify-center gap-2">
              {col.cells.map((cell, i) => (
                <CellRender key={`${col.depth}-${i}`} cell={cell} feederIdx={feederIdx} />
              ))}
            </div>
          </div>
        ))}
      </div>
      {hasProjections && (
        <p className="mt-1 text-[10px] italic text-text-muted">
          Dashed cells are projected from previous-round winners using draw position.
        </p>
      )}
    </div>
  );
}

function CellRender({
  cell,
  feederIdx,
}: {
  cell: Cell;
  feederIdx: Map<string, MatchSummary>;
}) {
  if (cell.kind === "match") return <MatchCell match={cell.match} feederIdx={feederIdx} />;
  if (cell.kind === "projected") return <ProjectedCell p1={cell.p1} p2={cell.p2} />;
  return <PlaceholderCell />;
}

/** Decide whether to swap p1/p2 display so the top of the cell shows
 * the player who came from the upper feeder. Returns false for leaf-
 * round cells (no feeder exists) or when feeder data is incomplete. */
function shouldSwapToFeederOrder(
  match: MatchSummary,
  feederIdx: Map<string, MatchSummary>,
): boolean {
  if (match.bracket_position == null || !match.round) return false;
  const deeper = DEEPER_ROUND[match.round.toUpperCase()];
  if (!deeper) return false;
  const topFeeder = feederIdx.get(`${deeper}|${2 * match.bracket_position}`);
  if (!topFeeder) return false;
  const topWinner =
    topFeeder.winner_slot === 1 ? topFeeder.player1 :
    topFeeder.winner_slot === 2 ? topFeeder.player2 : null;
  if (!topWinner) return false;
  // Top feeder's winner is our current match's player2 → that player
  // should display on top of the cell; swap.
  return match.player2?.slug === topWinner.slug;
}

function MatchCell({
  match,
  feederIdx,
}: {
  match: MatchSummary;
  feederIdx: Map<string, MatchSummary>;
}) {
  const swap = shouldSwapToFeederOrder(match, feederIdx);

  const topPlayer = swap ? match.player2 : match.player1;
  const bottomPlayer = swap ? match.player1 : match.player2;
  const topSeed = swap ? match.player2_seed : match.player1_seed;
  const bottomSeed = swap ? match.player1_seed : match.player2_seed;

  const sets = (match.score?.trim().split(/\s+/) ?? []).slice(0, 5);
  const origP1 = sets.map((s) => s.split("-")[0] ?? "");
  const origP2 = sets.map((s) => s.split("-")[1] ?? "");
  const topSets = swap ? origP2 : origP1;
  const bottomSets = swap ? origP1 : origP2;

  const finished = match.status === "finished";
  const isLive = match.status === "live";
  const isSuspended = match.status === "suspended";
  const topWon = finished && match.winner_slot === (swap ? 2 : 1);
  const bottomWon = finished && match.winner_slot === (swap ? 1 : 2);

  return (
    <Link
      href={`/matches/${match.id}`}
      className="block overflow-hidden rounded-md border border-ink-700 bg-ink-900 transition hover:border-ink-600 hover:bg-ink-800"
    >
      <Row
        name={topPlayer?.full_name ?? "TBD"}
        seed={topSeed}
        sets={topSets}
        bold={topWon}
        dim={bottomWon}
        winner={topWon}
      />
      <div className="border-t border-ink-700/60" />
      <Row
        name={bottomPlayer?.full_name ?? "TBD"}
        seed={bottomSeed}
        sets={bottomSets}
        bold={bottomWon}
        dim={topWon}
        winner={bottomWon}
      />
      {isLive && (
        <div className="bg-accent/10 px-2 py-0.5 text-center text-[9px] font-bold uppercase tracking-wider text-accent">
          Live
        </div>
      )}
      {isSuspended && (
        <div className="bg-amber-400/15 px-2 py-0.5 text-center text-[9px] font-bold uppercase tracking-wider text-amber-400">
          Suspended
        </div>
      )}
    </Link>
  );
}

function PlaceholderCell() {
  return (
    <div className="overflow-hidden rounded-md border border-dashed border-ink-700/60 bg-ink-900/40">
      <PlaceholderRow />
      <div className="border-t border-ink-700/30" />
      <PlaceholderRow />
    </div>
  );
}

function PlaceholderRow() {
  return (
    <div className="flex items-center px-2 py-1.5">
      <span className="text-xs italic text-text-muted/70">TBD</span>
    </div>
  );
}

function ProjectedCell({ p1, p2 }: { p1: PlayerSummary | null; p2: PlayerSummary | null }) {
  return (
    <div className="overflow-hidden rounded-md border border-dashed border-ink-600 bg-ink-900/60">
      <ProjectedRow player={p1} />
      <div className="border-t border-ink-700/40" />
      <ProjectedRow player={p2} />
    </div>
  );
}

function ProjectedRow({ player }: { player: PlayerSummary | null }) {
  return (
    <div className="flex items-center px-2 py-1.5">
      <span className="truncate text-xs italic text-text-secondary">
        {player?.full_name ?? "TBD"}
      </span>
    </div>
  );
}

function Row({
  name,
  seed,
  sets,
  bold,
  dim,
  winner,
}: {
  name: string;
  seed?: number | null;
  sets: string[];
  bold: boolean;
  dim: boolean;
  winner: boolean;
}) {
  return (
    <div
      className={`flex items-center gap-1 px-2 py-1.5 text-xs ${dim ? "opacity-50" : ""}`}
    >
      <span className={`min-w-0 flex-1 truncate ${bold ? "font-bold text-text-primary" : "text-text-secondary"}`}>
        {winner && <span className="mr-1 text-accent">▸</span>}
        {seed != null && (
          <span className="mr-1 text-[10px] text-text-muted tabular-nums">[{seed}]</span>
        )}
        {name}
      </span>
      <div className="flex items-center gap-1 tabular-nums">
        {sets.map((s, i) => (
          <span
            key={i}
            className={`w-3 text-right text-[11px] ${bold ? "font-bold text-text-primary" : "text-text-secondary"}`}
          >
            {formatSetScore(s)}
          </span>
        ))}
      </div>
    </div>
  );
}
