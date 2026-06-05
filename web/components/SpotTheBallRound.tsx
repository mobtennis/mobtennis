"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { SpotTheBallPuzzle } from "@/lib/api";

/**
 * Round-mode play: walk through N puzzles back-to-back, score
 * cumulatively, show a summary at the end. Designed around the
 * insight that each puzzle takes ~10 seconds — daily-one-puzzle
 * was leaving most of the entertainment on the table.
 *
 * Storage:
 *   - mob:stb:round:{seed}      → completed round summary (per seed)
 *   - mob:stb:scores:v1         → individual puzzle scores (shared
 *     with the archive view; saved on first attempt only)
 *
 * Replaying a completed round shows the summary first with a
 * "Replay (no score saved)" option for practice.
 */

const ROUND_KEY_PREFIX = "mob:stb:round:";
const SCORES_KEY = "mob:stb:scores:v1";

type PuzzleResult = {
  puzzle_date: string;
  guess_x_pct: number;
  guess_y_pct: number;
  distance_pct: number;
  band: "perfect" | "close" | "miss";
  points: number;
};

type RoundSummary = {
  seed: string;
  results: PuzzleResult[];
  total_points: number;
  completed_at: string;
};

type StoredIndividualResult = {
  date: string;
  guess_x_pct: number;
  guess_y_pct: number;
  distance_pct: number;
  band: "perfect" | "close" | "miss";
  played_at: string;
};


function loadRound(seed: string): RoundSummary | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(ROUND_KEY_PREFIX + seed);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveRound(round: RoundSummary): void {
  localStorage.setItem(ROUND_KEY_PREFIX + round.seed, JSON.stringify(round));
}

function saveIndividualResultIfFirst(r: PuzzleResult): void {
  try {
    const all: Record<string, StoredIndividualResult> = JSON.parse(
      localStorage.getItem(SCORES_KEY) || "{}",
    );
    if (all[r.puzzle_date]) return;  // first attempt wins
    all[r.puzzle_date] = {
      date: r.puzzle_date,
      guess_x_pct: r.guess_x_pct,
      guess_y_pct: r.guess_y_pct,
      distance_pct: r.distance_pct,
      band: r.band,
      played_at: new Date().toISOString(),
    };
    localStorage.setItem(SCORES_KEY, JSON.stringify(all));
  } catch {
    /* ignore — localStorage might be disabled */
  }
}

function bandFor(distance_pct: number): PuzzleResult["band"] {
  if (distance_pct <= 3) return "perfect";
  if (distance_pct <= 7) return "close";
  return "miss";
}

function pointsFor(distance_pct: number): number {
  return Math.max(0, Math.round(100 - distance_pct * 7));
}


export function SpotTheBallRound({
  round,
}: {
  round: { seed: string; puzzles: SpotTheBallPuzzle[] };
}) {
  const [savedSummary, setSavedSummary] = useState<RoundSummary | null>(null);
  // `practice` is set to true when the user replays a completed round —
  // we don't overwrite the saved summary in that mode.
  const [practice, setPractice] = useState(false);
  const [idx, setIdx] = useState(0);
  const [results, setResults] = useState<PuzzleResult[]>([]);
  const [guess, setGuess] = useState<{ x_pct: number; y_pct: number } | null>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);

  // Load prior result on mount — if a round under this seed is
  // already played, drop straight into the summary view.
  useEffect(() => {
    const prior = loadRound(round.seed);
    if (prior) setSavedSummary(prior);
  }, [round.seed]);

  const total = round.puzzles.length;
  const current = round.puzzles[idx] ?? null;
  const revealed = guess !== null;

  const distanceForGuess = useMemo(() => {
    if (!guess || !current) return null;
    const dx = guess.x_pct - current.ball_x_pct;
    const dy = guess.y_pct - current.ball_y_pct;
    return Math.hypot(dx, dy);
  }, [guess, current]);

  const cumulativePoints = useMemo(
    () => results.reduce((s, r) => s + r.points, 0),
    [results],
  );

  const onImageClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (revealed || !current) return;
    const el = imgRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const x_pct = ((e.clientX - rect.left) / rect.width) * 100;
    const y_pct = ((e.clientY - rect.top) / rect.height) * 100;
    setGuess({ x_pct, y_pct });
  }, [revealed, current]);

  const advance = useCallback(() => {
    if (!current || !guess || distanceForGuess === null) return;
    const result: PuzzleResult = {
      puzzle_date: current.puzzle_date,
      guess_x_pct: guess.x_pct,
      guess_y_pct: guess.y_pct,
      distance_pct: distanceForGuess,
      band: bandFor(distanceForGuess),
      points: pointsFor(distanceForGuess),
    };
    if (!practice) saveIndividualResultIfFirst(result);

    const next = [...results, result];
    setResults(next);
    setGuess(null);

    if (idx + 1 < total) {
      setIdx(idx + 1);
    } else {
      // Round complete.
      const summary: RoundSummary = {
        seed: round.seed,
        results: next,
        total_points: next.reduce((s, r) => s + r.points, 0),
        completed_at: new Date().toISOString(),
      };
      if (!practice) saveRound(summary);
      setSavedSummary(summary);
    }
  }, [current, guess, distanceForGuess, idx, total, results, practice, round.seed]);

  // --- Summary view -----------------------------------------------

  if (savedSummary && !practice) {
    return (
      <RoundSummaryView
        summary={savedSummary}
        puzzles={round.puzzles}
        onReplay={() => {
          setPractice(true);
          setSavedSummary(null);
          setIdx(0);
          setResults([]);
          setGuess(null);
        }}
      />
    );
  }

  if (!current) {
    return <p className="text-sm text-text-muted">No puzzles in this round.</p>;
  }

  // --- Play view --------------------------------------------------

  return (
    <div className="space-y-4">
      <RoundHeader
        idx={idx}
        total={total}
        cumulative={cumulativePoints}
        practice={practice}
      />

      <div className="text-xs uppercase tracking-wider text-text-muted">
        {current.puzzle_date} · {current.caption}
      </div>

      <div
        onClick={onImageClick}
        className={`relative w-full select-none overflow-hidden rounded-lg border border-ink-700 bg-ink-900 ${
          revealed ? "cursor-default" : "cursor-crosshair"
        }`}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          ref={imgRef}
          src={revealed && current.original_image_url ? current.original_image_url : current.image_url}
          alt={current.caption}
          className="block h-auto w-full"
          draggable={false}
        />
        {guess && <Pin x_pct={guess.x_pct} y_pct={guess.y_pct} variant={bandFor(distanceForGuess ?? 999)} />}
        {revealed && (
          <Pin x_pct={current.ball_x_pct} y_pct={current.ball_y_pct} variant="truth" />
        )}
        {revealed && guess && bandFor(distanceForGuess ?? 0) !== "perfect" && (
          <GuessLine
            from={guess}
            to={{ x_pct: current.ball_x_pct, y_pct: current.ball_y_pct }}
          />
        )}
      </div>

      {revealed && distanceForGuess !== null && (
        <ResultPanel distance_pct={distanceForGuess} />
      )}

      {revealed && (
        <button
          type="button"
          onClick={advance}
          className="w-full rounded-md bg-accent px-4 py-3 text-sm font-bold uppercase tracking-wider text-white hover:bg-accent-dim"
        >
          {idx + 1 < total ? `Next (${idx + 2}/${total}) →` : "Finish round →"}
        </button>
      )}

      {(current.credit || current.source_url) && (
        <div className="text-[11px] text-text-muted">
          {current.credit && <span>Photo: {current.credit}</span>}
          {current.source_url && (
            <>
              {" · "}
              <a
                href={current.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="underline decoration-dotted underline-offset-2 hover:text-text-secondary"
              >
                source
              </a>
            </>
          )}
        </div>
      )}
    </div>
  );
}


function RoundHeader({
  idx,
  total,
  cumulative,
  practice,
}: {
  idx: number;
  total: number;
  cumulative: number;
  practice: boolean;
}) {
  return (
    <header className="flex items-baseline justify-between gap-3">
      <div>
        <div className="text-[10px] font-bold uppercase tracking-wider text-accent">
          {practice ? "Practice" : "Today's round"}
        </div>
        <h1 className="mt-1 text-2xl font-bold tracking-tight">
          Spot the ball · {idx + 1} of {total}
        </h1>
      </div>
      <div className="text-right">
        <div className="text-[10px] uppercase tracking-wider text-text-muted">
          So far
        </div>
        <div className="text-2xl font-bold tabular-nums text-text-primary">
          {cumulative}
        </div>
      </div>
    </header>
  );
}


function RoundSummaryView({
  summary,
  puzzles,
  onReplay,
}: {
  summary: RoundSummary;
  puzzles: SpotTheBallPuzzle[];
  onReplay: () => void;
}) {
  const max_possible = puzzles.length * 100;
  return (
    <div className="space-y-5">
      <header>
        <div className="text-[10px] font-bold uppercase tracking-wider text-accent">
          Round complete
        </div>
        <h1 className="mt-1 text-3xl font-bold tracking-tight">
          {summary.total_points}{" "}
          <span className="text-lg font-medium text-text-muted">/ {max_possible}</span>
        </h1>
      </header>

      <ul className="divide-y divide-ink-700 overflow-hidden rounded-lg border border-ink-700 bg-ink-900">
        {summary.results.map((r) => {
          const p = puzzles.find((pp) => pp.puzzle_date === r.puzzle_date);
          const tone =
            r.band === "perfect"
              ? "text-emerald-300"
              : r.band === "close"
                ? "text-amber-300"
                : "text-red-300";
          return (
            <li key={r.puzzle_date} className="flex items-center gap-3 p-3">
              {p && (
                /* eslint-disable-next-line @next/next/no-img-element */
                <img
                  src={p.image_url}
                  alt=""
                  className="h-12 w-20 shrink-0 rounded object-cover"
                />
              )}
              <div className="flex-1 min-w-0">
                <div className="line-clamp-1 text-sm font-medium text-text-primary">
                  {p?.caption ?? r.puzzle_date}
                </div>
                <div className={`text-xs ${tone}`}>
                  {r.band} · {r.distance_pct.toFixed(1)}% off
                </div>
              </div>
              <div className="shrink-0 text-right">
                <div className="text-lg font-bold tabular-nums">{r.points}</div>
                <div className="text-[10px] uppercase tracking-wider text-text-muted">
                  pts
                </div>
              </div>
            </li>
          );
        })}
      </ul>

      <button
        type="button"
        onClick={onReplay}
        className="w-full rounded-md border border-ink-700 px-4 py-3 text-sm font-medium text-text-secondary hover:bg-ink-800"
      >
        Replay this round (practice — no score saved)
      </button>
    </div>
  );
}


// --- Pin / line / result panel (mirrors SpotTheBall.tsx) -------------

function Pin({
  x_pct,
  y_pct,
  variant,
}: {
  x_pct: number;
  y_pct: number;
  variant: "perfect" | "close" | "miss" | "truth";
}) {
  const stroke =
    variant === "perfect"
      ? "stroke-emerald-300"
      : variant === "close"
        ? "stroke-amber-300"
        : variant === "miss"
          ? "stroke-red-300"
          : "stroke-accent";
  const dot =
    variant === "perfect"
      ? "fill-emerald-300"
      : variant === "close"
        ? "fill-amber-300"
        : variant === "miss"
          ? "fill-red-300"
          : "fill-accent";
  return (
    <svg
      className="pointer-events-none absolute h-8 w-8 -translate-x-1/2 -translate-y-1/2 drop-shadow-[0_1px_2px_rgba(0,0,0,0.6)]"
      style={{ left: `${x_pct}%`, top: `${y_pct}%` }}
      viewBox="-20 -20 40 40"
      aria-hidden
    >
      <circle r="8" fill="none" className={stroke} strokeWidth="1.4" />
      <line x1="-15" y1="0" x2="-3" y2="0" className={stroke} strokeWidth="1.4" strokeLinecap="round" />
      <line x1="3" y1="0" x2="15" y2="0" className={stroke} strokeWidth="1.4" strokeLinecap="round" />
      <line x1="0" y1="-15" x2="0" y2="-3" className={stroke} strokeWidth="1.4" strokeLinecap="round" />
      <line x1="0" y1="3" x2="0" y2="15" className={stroke} strokeWidth="1.4" strokeLinecap="round" />
      <circle r="1.2" className={dot} />
    </svg>
  );
}


function GuessLine({
  from,
  to,
}: {
  from: { x_pct: number; y_pct: number };
  to: { x_pct: number; y_pct: number };
}) {
  return (
    <svg
      className="pointer-events-none absolute inset-0 h-full w-full"
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      aria-hidden
    >
      <line
        x1={from.x_pct}
        y1={from.y_pct}
        x2={to.x_pct}
        y2={to.y_pct}
        stroke="rgba(255,255,255,0.6)"
        strokeWidth="0.3"
        strokeDasharray="0.8 0.6"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}


function ResultPanel({ distance_pct }: { distance_pct: number }) {
  const band = bandFor(distance_pct);
  const points = pointsFor(distance_pct);
  const headline =
    band === "perfect" ? "🎾  Direct hit" : band === "close" ? "👀  Close" : "💀  Miss";
  const tone =
    band === "perfect"
      ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
      : band === "close"
        ? "border-amber-500/40 bg-amber-500/10 text-amber-300"
        : "border-red-500/40 bg-red-500/10 text-red-300";
  return (
    <div className={`rounded-md border p-4 ${tone}`}>
      <div className="text-lg font-semibold">{headline}</div>
      <div className="mt-1 text-xs uppercase tracking-wider opacity-80">
        {distance_pct.toFixed(1)}% off · {points} pts
      </div>
    </div>
  );
}
