"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { API_BASE, type SpotTheBallPuzzle } from "@/lib/api";

/**
 * Spot-the-Ball play UI.
 *
 * Mechanic: user clicks anywhere on the photo. Distance from the true
 * ball is computed in image-percentage space (so the threshold is
 * consistent at any rendered size). Outcome bands:
 *
 *   ≤ 3% of image diagonal → "perfect", snap, big celebration
 *   ≤ 7%                  → "close", show both pins, modest praise
 *   > 7%                  → "miss", reveal real ball, sad trombone
 *
 * Persistence: one result per puzzle_date stored in localStorage so
 * past plays are remembered without an account. Replaying a puzzle
 * is allowed but the saved score is the first attempt only — the
 * enclose.horse model.
 *
 * Calibration mode (?calibrate=ADMIN_KEY): clicking the photo POSTs
 * the click coords to /api/admin/spot-the-ball/{date}/ball, which sets
 * the true ball position on the row. Used when seeding new puzzles —
 * beats trying to label coordinates by editing JSON.
 */

const STORAGE_KEY = "mob:stb:scores:v1";

type StoredResult = {
  date: string;
  guess_x_pct: number;
  guess_y_pct: number;
  distance_pct: number;  // distance in image-percent units
  band: "perfect" | "close" | "miss";
  played_at: string;     // ISO timestamp
};

function loadAllResults(): Record<string, StoredResult> {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
  } catch {
    return {};
  }
}

function saveResult(r: StoredResult): void {
  const all = loadAllResults();
  // Only the first attempt counts — don't overwrite an existing
  // record. (Replay still works visually; the score just doesn't
  // change.)
  if (all[r.date]) return;
  all[r.date] = r;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(all));
}


export function SpotTheBall({
  puzzle,
  calibrateKey,
}: {
  puzzle: SpotTheBallPuzzle;
  calibrateKey?: string | null;
}) {
  const imgRef = useRef<HTMLImageElement | null>(null);
  const [guess, setGuess] = useState<{ x_pct: number; y_pct: number } | null>(null);
  const [revealed, setRevealed] = useState(false);
  // In calibration mode, seed the marker from the row's currently-saved
  // ball coords so an operator returning to a previously-calibrated
  // puzzle SEES the saved position (rather than a blank canvas, which
  // made it look like nothing had been saved).
  const [calibrated, setCalibrated] = useState<{ x_pct: number; y_pct: number } | null>(
    calibrateKey
      ? { x_pct: puzzle.ball_x_pct, y_pct: puzzle.ball_y_pct }
      : null,
  );
  const [calibrateError, setCalibrateError] = useState<string | null>(null);

  // On mount, surface any prior score for this puzzle so a returning
  // visitor lands on their previous reveal rather than a clean slate.
  useEffect(() => {
    const prior = loadAllResults()[puzzle.puzzle_date];
    if (prior) {
      setGuess({ x_pct: prior.guess_x_pct, y_pct: prior.guess_y_pct });
      setRevealed(true);
    }
  }, [puzzle.puzzle_date]);

  // Compute the diagonal-relative distance in % units. Squared distance
  // would be cheaper but Math.hypot is fine here — we run it once per
  // click, not in a hot loop.
  const result = useMemo(() => {
    if (!guess) return null;
    const dx = guess.x_pct - puzzle.ball_x_pct;
    const dy = guess.y_pct - puzzle.ball_y_pct;
    const distance_pct = Math.hypot(dx, dy);
    let band: StoredResult["band"];
    if (distance_pct <= 3) band = "perfect";
    else if (distance_pct <= 7) band = "close";
    else band = "miss";
    return { distance_pct, band };
  }, [guess, puzzle.ball_x_pct, puzzle.ball_y_pct]);

  const onImageClick = async (e: React.MouseEvent<HTMLDivElement>) => {
    const el = imgRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const x_pct = ((e.clientX - rect.left) / rect.width) * 100;
    const y_pct = ((e.clientY - rect.top) / rect.height) * 100;

    if (calibrateKey) {
      // Calibration mode — POST to admin endpoint and store locally.
      setCalibrateError(null);
      try {
        const url = `${API_BASE}/api/admin/spot-the-ball/${puzzle.puzzle_date}/ball?key=${encodeURIComponent(calibrateKey)}`;
        const res = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ball_x_pct: x_pct, ball_y_pct: y_pct }),
        });
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
        setCalibrated({ x_pct, y_pct });
      } catch (err) {
        setCalibrateError(String(err));
      }
      return;
    }

    if (revealed) return; // already submitted — clicking again is a no-op
    setGuess({ x_pct, y_pct });
    setRevealed(true);
  };

  // Persist on first reveal.
  useEffect(() => {
    if (!revealed || !guess || !result) return;
    saveResult({
      date: puzzle.puzzle_date,
      guess_x_pct: guess.x_pct,
      guess_y_pct: guess.y_pct,
      distance_pct: result.distance_pct,
      band: result.band,
      played_at: new Date().toISOString(),
    });
  }, [revealed, guess, result, puzzle.puzzle_date]);

  return (
    <div className="space-y-4">
      <div className="text-xs uppercase tracking-wider text-text-muted">
        {puzzle.puzzle_date}
      </div>
      <h1 className="text-2xl font-bold tracking-tight">
        {calibrateKey ? "Calibrate the ball" : "Spot the ball"}
      </h1>
      <p className="text-sm text-text-secondary">
        {calibrateKey
          ? "Click where the ball is. Saves immediately."
          : revealed
            ? "Result below."
            : "Where do you think the ball is? One click locks it in."}
      </p>

      <div
        onClick={onImageClick}
        className={`relative w-full select-none overflow-hidden rounded-lg border border-ink-700 bg-ink-900 ${
          revealed && !calibrateKey ? "cursor-default" : "cursor-crosshair"
        }`}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          ref={imgRef}
          src={puzzle.image_url}
          alt={puzzle.caption}
          className="block h-auto w-full"
          draggable={false}
        />

        {/* Calibration mode: just show the click as a green dot. */}
        {calibrateKey && calibrated && (
          <Pin x_pct={calibrated.x_pct} y_pct={calibrated.y_pct} variant="calibrated" />
        )}

        {/* Play mode: show guess + (after reveal) the true position. */}
        {!calibrateKey && guess && (
          <Pin x_pct={guess.x_pct} y_pct={guess.y_pct} variant={result?.band ?? "miss"} />
        )}
        {!calibrateKey && revealed && (
          <Pin
            x_pct={puzzle.ball_x_pct}
            y_pct={puzzle.ball_y_pct}
            variant="truth"
          />
        )}

        {/* Draw a line between guess and truth when not perfect. Helps
            you see HOW you misjudged the physics. */}
        {!calibrateKey && revealed && guess && result?.band !== "perfect" && (
          <GuessLine
            from={guess}
            to={{ x_pct: puzzle.ball_x_pct, y_pct: puzzle.ball_y_pct }}
          />
        )}
      </div>

      {/* Result panel — only shown in play mode after reveal. */}
      {!calibrateKey && revealed && result && (
        <ResultPanel result={result} />
      )}

      {/* Calibration feedback. Shows the currently-saved coords on
          load (from puzzle props) and updates after each click + save. */}
      {calibrateKey && calibrated && !calibrateError && (
        <div className="rounded-md border border-emerald-500/40 bg-emerald-500/10 p-3 text-sm text-emerald-300">
          Ball at ({calibrated.x_pct.toFixed(1)}%, {calibrated.y_pct.toFixed(1)}%).
          Click anywhere on the photo to re-place; each click saves
          immediately.
        </div>
      )}
      {calibrateKey && calibrateError && (
        <div className="rounded-md border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">
          Calibration failed: {calibrateError}
        </div>
      )}

      {/* Credit / source. */}
      {(puzzle.credit || puzzle.source_url) && (
        <div className="text-[11px] text-text-muted">
          {puzzle.credit && <span>Photo: {puzzle.credit}</span>}
          {puzzle.source_url && (
            <>
              {" · "}
              <a
                href={puzzle.source_url}
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


function Pin({
  x_pct,
  y_pct,
  variant,
}: {
  x_pct: number;
  y_pct: number;
  variant: "perfect" | "close" | "miss" | "truth" | "calibrated";
}) {
  const color =
    variant === "perfect"
      ? "bg-emerald-400 ring-emerald-300"
      : variant === "close"
        ? "bg-amber-400 ring-amber-300"
        : variant === "miss"
          ? "bg-red-400 ring-red-300"
          : variant === "truth"
            ? "bg-accent ring-accent"
            : "bg-emerald-400 ring-emerald-300";
  const ring = variant === "truth" ? "ring-4" : "ring-2";
  return (
    <span
      className={`pointer-events-none absolute h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full ${color} ${ring} ring-offset-2 ring-offset-ink-900/60 shadow-lg`}
      style={{ left: `${x_pct}%`, top: `${y_pct}%` }}
      aria-hidden
    />
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


function ResultPanel({
  result,
}: {
  result: { distance_pct: number; band: "perfect" | "close" | "miss" };
}) {
  const { band, distance_pct } = result;
  const headline =
    band === "perfect"
      ? "🎾  Direct hit"
      : band === "close"
        ? "👀  Close"
        : "💀  Miss";
  const score = Math.max(0, Math.round(100 - distance_pct * 7));
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
        {distance_pct.toFixed(1)}% off · {score} pts
      </div>
    </div>
  );
}
