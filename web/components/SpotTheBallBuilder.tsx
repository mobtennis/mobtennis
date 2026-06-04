"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { API_BASE } from "@/lib/api";

/**
 * Admin builder for the Spot the Ball game. Walks the operator
 * through the pool of professional-player Wikimedia photos,
 * one image at a time:
 *
 *   - SKIP   → drops the image from the pool permanently.
 *   - CLICK  → POSTs the ball coords as a scheduled future puzzle.
 *              Backend auto-assigns the next available day.
 *
 * After either action the page advances to the next candidate
 * without reload.
 *
 * Scheduled puzzles aren't public yet — they have is_published=False
 * until the local Replicate processor (process_spot_the_ball_images.py)
 * runs over the queue, inpaints the ball out of each photo, saves
 * to web/public/spot-the-ball/, and flips the flag.
 */

type Candidate = {
  player_image_id: number;
  image_url: string;
  player_slug: string;
  player_name: string;
  suggested_caption: string;
  credit: string | null;
  license_url: string | null;
  source_url: string | null;
  width: number | null;
  height: number | null;
};

type Stats = {
  candidates_remaining: number;
  queued: number;
  published: number;
  skipped: number;
};

type NextResponse = {
  candidate: Candidate | null;
  stats: Stats;
};

type ScheduleResponse = {
  scheduled_date: string;
  next_candidate: Candidate | null;
  stats: Stats;
};


export function SpotTheBallBuilder({ adminKey }: { adminKey: string }) {
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastScheduled, setLastScheduled] = useState<string | null>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);

  const loadNext = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `${API_BASE}/api/admin/spot-the-ball/builder/next?key=${encodeURIComponent(adminKey)}`,
      );
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const data: NextResponse = await res.json();
      setCandidate(data.candidate);
      setStats(data.stats);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [adminKey]);

  useEffect(() => {
    loadNext();
  }, [loadNext]);

  const onSkip = async () => {
    if (!candidate || pending) return;
    setPending(true);
    setError(null);
    try {
      const res = await fetch(
        `${API_BASE}/api/admin/spot-the-ball/builder/skip?key=${encodeURIComponent(adminKey)}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ player_image_id: candidate.player_image_id }),
        },
      );
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const data: NextResponse = await res.json();
      setCandidate(data.candidate);
      setStats(data.stats);
    } catch (e) {
      setError(String(e));
    } finally {
      setPending(false);
    }
  };

  const onImageClick = async (e: React.MouseEvent<HTMLDivElement>) => {
    if (!candidate || pending) return;
    const el = imgRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const x_pct = ((e.clientX - rect.left) / rect.width) * 100;
    const y_pct = ((e.clientY - rect.top) / rect.height) * 100;
    setPending(true);
    setError(null);
    try {
      const res = await fetch(
        `${API_BASE}/api/admin/spot-the-ball/builder/schedule?key=${encodeURIComponent(adminKey)}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            player_image_id: candidate.player_image_id,
            ball_x_pct: x_pct,
            ball_y_pct: y_pct,
          }),
        },
      );
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const data: ScheduleResponse = await res.json();
      setLastScheduled(`${data.scheduled_date} · ${candidate.player_name}`);
      setCandidate(data.next_candidate);
      setStats(data.stats);
    } catch (e) {
      setError(String(e));
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="space-y-4 p-3">
      <header className="space-y-1">
        <h1 className="text-xl font-bold tracking-tight">Spot the ball · builder</h1>
        <p className="text-xs text-text-muted">
          Click the ball to schedule the image as a future puzzle. Skip
          to drop it from the pool. Scheduled puzzles enter the queue
          and need a local Replicate run to inpaint before they go
          public.
        </p>
      </header>

      {stats && (
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          <Stat label="Candidates remaining" value={stats.candidates_remaining} />
          <Stat label="Queued (need processing)" value={stats.queued} />
          <Stat label="Published" value={stats.published} />
          <Stat label="Skipped" value={stats.skipped} />
        </div>
      )}

      {lastScheduled && (
        <div className="rounded-md border border-emerald-500/40 bg-emerald-500/10 p-3 text-sm text-emerald-300">
          Scheduled: {lastScheduled}
        </div>
      )}

      {error && (
        <div className="rounded-md border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {loading && <p className="text-sm text-text-muted">Loading next candidate…</p>}

      {!loading && !candidate && (
        <div className="rounded-md border border-ink-700 bg-ink-900 p-4 text-sm">
          <p className="font-semibold">Pool is empty.</p>
          <p className="mt-1 text-text-secondary">
            All eligible PlayerImages are either scheduled or skipped.
            Re-enrich the photo collection if you want more candidates.
          </p>
        </div>
      )}

      {!loading && candidate && (
        <>
          <div className="text-xs text-text-muted">
            <span className="font-semibold text-text-primary">{candidate.player_name}</span>
            {candidate.credit && <> · {candidate.credit}</>}
            {candidate.width && candidate.height && (
              <> · {candidate.width}×{candidate.height}</>
            )}
            {candidate.source_url && (
              <>
                {" · "}
                <a
                  href={candidate.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline decoration-dotted underline-offset-2 hover:text-text-secondary"
                >
                  Commons file page
                </a>
              </>
            )}
          </div>

          <div
            onClick={onImageClick}
            className={`relative w-full select-none overflow-hidden rounded-lg border border-ink-700 bg-ink-900 ${
              pending ? "cursor-wait opacity-70" : "cursor-crosshair"
            }`}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              ref={imgRef}
              src={candidate.image_url}
              alt={candidate.player_name}
              className="block h-auto w-full"
              draggable={false}
            />
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={pending}
              onClick={onSkip}
              className="rounded-md border border-ink-700 px-4 py-2 text-sm font-medium text-text-secondary hover:bg-ink-800 disabled:opacity-50"
            >
              Skip — no good
            </button>
            <span className="self-center text-xs text-text-muted">
              (Or click the ball in the photo to schedule)
            </span>
          </div>
        </>
      )}
    </div>
  );
}


function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-ink-700 bg-ink-900 p-3">
      <div className="text-[10px] uppercase tracking-wider text-text-muted">{label}</div>
      <div className="mt-1 text-2xl font-bold tabular-nums">{value}</div>
    </div>
  );
}
