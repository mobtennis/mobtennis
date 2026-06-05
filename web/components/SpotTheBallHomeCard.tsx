"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { API_BASE } from "@/lib/api";

/**
 * Home-page card for the daily Spot the Ball round. Three states:
 *
 *   not played → "Today's round · 5 photos, can you place the ball?"
 *                 with a CTA to /play/spot-the-ball
 *   played     → score + pattern of squares
 *
 * Lives between the first ongoing tournament block and the rest of
 * "Happening now" — premium real estate without burying the live
 * tournament that's actually the headline.
 *
 * Pure client component because the played/unplayed state lives in
 * localStorage. Server can't know it.
 */

type SavedSummary = {
  set_id: number;
  total_points: number;
  results: Array<{ band: "perfect" | "close" | "miss" }>;
};

const SET_KEY_PREFIX = "mob:stb:set:";


export function SpotTheBallHomeCard() {
  // todaySetId is whatever set the /today endpoint will resolve to.
  // We fetch it lazily on mount so we can tell if the player has
  // already finished it.
  const [todaySetId, setTodaySetId] = useState<number | null>(null);
  const [summary, setSummary] = useState<SavedSummary | null>(null);
  const [imageCount, setImageCount] = useState(5);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/api/spot-the-ball/today`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data: { id: number; images: unknown[] } | null) => {
        if (cancelled || !data) {
          setLoaded(true);
          return;
        }
        setTodaySetId(data.id);
        setImageCount(data.images.length || 5);
        try {
          const raw = localStorage.getItem(SET_KEY_PREFIX + data.id);
          if (raw) {
            const parsed = JSON.parse(raw) as SavedSummary;
            setSummary(parsed);
          }
        } catch {
          /* ignore */
        }
        setLoaded(true);
      })
      .catch(() => setLoaded(true));
    return () => {
      cancelled = true;
    };
  }, []);

  // Until we know whether there's a set, render a placeholder that
  // takes roughly the right amount of space so the layout doesn't
  // jump after hydration.
  if (!loaded) {
    return <div className="h-24 rounded-lg border border-dashed border-ink-700" aria-hidden />;
  }

  if (todaySetId === null) {
    // No set live yet — don't render the card (game hasn't reached
    // this player's time window yet).
    return null;
  }

  const maxPoints = imageCount * 100;
  const href = `/play/spot-the-ball`;
  const completed = !!summary;

  if (completed) {
    return (
      <Link
        href={href}
        className="group block overflow-hidden rounded-lg border border-emerald-500/30 bg-ink-900 shadow-card transition hover:border-emerald-500/60"
      >
        <div className="flex items-stretch gap-4 p-4">
          <Trophy />
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            <div className="text-[10px] font-bold uppercase tracking-wider text-emerald-300">
              Spot the ball · today's round
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold tabular-nums">
                {summary!.total_points}
              </span>
              <span className="text-sm text-text-muted">/ {maxPoints}</span>
            </div>
            <div className="mt-1 flex gap-1">
              {summary!.results.map((r, i) => {
                const bg =
                  r.band === "perfect"
                    ? "bg-emerald-500"
                    : r.band === "close"
                      ? "bg-amber-500"
                      : "bg-red-500";
                return <span key={i} className={`h-3 w-3 rounded-sm ${bg}`} />;
              })}
            </div>
          </div>
          <div className="self-center text-xs font-semibold text-accent">
            Review →
          </div>
        </div>
      </Link>
    );
  }

  return (
    <Link
      href={href}
      className="group block overflow-hidden rounded-lg border border-ink-700 bg-ink-900 shadow-card transition hover:border-accent/60"
    >
      <div className="flex items-stretch gap-4 p-4">
        <Ball />
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <div className="text-[10px] font-bold uppercase tracking-wider text-accent">
            Spot the ball · today's round
          </div>
          <div className="text-base font-semibold text-text-primary">
            {imageCount} photos, ball removed. Can you click it?
          </div>
          <div className="text-xs text-text-muted">
            Same 5 photos for every player today.
          </div>
        </div>
        <div className="self-center rounded-md bg-accent px-3 py-2 text-[11px] font-bold uppercase tracking-wider text-white group-hover:bg-accent-dim">
          Play →
        </div>
      </div>
    </Link>
  );
}


function Ball() {
  return (
    <div
      aria-hidden
      className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-accent/15 text-2xl"
    >
      🎾
    </div>
  );
}


function Trophy() {
  return (
    <div
      aria-hidden
      className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-emerald-500/15 text-2xl"
    >
      🏆
    </div>
  );
}
