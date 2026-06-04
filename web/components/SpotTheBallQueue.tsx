"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { API_BASE } from "@/lib/api";

/**
 * Admin queue / verification page.
 *
 * Lists every puzzle the operator has ever scheduled, newest first,
 * with status badges so they can:
 *   - Glance at the queue (what's scheduled vs published)
 *   - Click any thumbnail → goes to that puzzle's calibrate page,
 *     where they can re-click the ball if the position drifted
 *   - Verify the inpaint result on a published puzzle by viewing
 *     the thumbnail directly here (the API returns the LIVE
 *     image_url, which is the inpainted version once processed)
 *
 * The status badges:
 *   QUEUED     — scheduled but Replicate hasn't run yet
 *   PUBLISHED  — inpainted, live to the public (or live on the
 *                scheduled date when it arrives)
 */

type QueueItem = {
  puzzle_date: string;
  caption: string;
  image_url: string;
  original_image_url: string | null;
  is_published: boolean;
  ball_x_pct: number | null;
  ball_y_pct: number | null;
};


export function SpotTheBallQueue({ adminKey }: { adminKey: string }) {
  const [items, setItems] = useState<QueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `${API_BASE}/api/admin/spot-the-ball/all?key=${encodeURIComponent(adminKey)}`,
      );
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      setItems(await res.json());
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [adminKey]);

  useEffect(() => {
    load();
  }, [load]);

  const queued = items.filter((i) => !i.is_published).length;
  const published = items.filter((i) => i.is_published).length;

  return (
    <div className="space-y-4 p-3">
      <header className="flex items-baseline justify-between gap-3">
        <h1 className="text-xl font-bold tracking-tight">Spot the ball · queue</h1>
        <Link
          href={`/admin/spot-the-ball/builder?key=${encodeURIComponent(adminKey)}`}
          className="text-sm font-medium text-accent hover:text-accent-dim"
        >
          Add more →
        </Link>
      </header>

      <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
        <Stat label="Queued (need processing)" value={queued} />
        <Stat label="Published" value={published} />
        <Stat label="Total" value={items.length} />
      </div>

      {queued > 0 && (
        <div className="rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-200">
          <p className="font-semibold">{queued} puzzle{queued > 1 ? "s" : ""} waiting on Replicate.</p>
          <p className="mt-1 text-xs opacity-90">
            Run locally:{" "}
            <code className="rounded bg-black/30 px-1.5 py-0.5">
              REPLICATE_API_TOKEN=… ADMIN_KEY=… python -m
              scripts.process_spot_the_ball_images --queue-only
            </code>
            {" "}then{" "}
            <code className="rounded bg-black/30 px-1.5 py-0.5">git push</code>.
          </p>
        </div>
      )}

      {error && (
        <div className="rounded-md border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {loading && <p className="text-sm text-text-muted">Loading…</p>}

      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {items.map((it) => (
          <li
            key={it.puzzle_date}
            className={`overflow-hidden rounded-lg border bg-ink-900 ${
              it.is_published ? "border-emerald-600/30" : "border-amber-600/40"
            }`}
          >
            <Link
              href={`/play/spot-the-ball/${it.puzzle_date}?calibrate=${encodeURIComponent(adminKey)}`}
              className="group block"
            >
              <div className="relative aspect-video w-full overflow-hidden bg-ink-950">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={it.image_url}
                  alt={it.caption}
                  className="h-full w-full object-cover transition-opacity group-hover:opacity-90"
                  loading="lazy"
                />
                <StatusBadge published={it.is_published} />
                {it.ball_x_pct != null && it.ball_y_pct != null && (
                  <BallPin x_pct={it.ball_x_pct} y_pct={it.ball_y_pct} />
                )}
              </div>
              <div className="p-2.5">
                <div className="text-[10px] uppercase tracking-wider text-text-muted">
                  {it.puzzle_date}
                </div>
                <div className="mt-0.5 line-clamp-1 text-sm font-medium text-text-primary">
                  {it.caption}
                </div>
              </div>
            </Link>
          </li>
        ))}
      </ul>

      {!loading && items.length === 0 && (
        <p className="text-sm text-text-muted">
          Nothing scheduled yet.{" "}
          <Link
            href={`/admin/spot-the-ball/builder?key=${encodeURIComponent(adminKey)}`}
            className="text-accent hover:text-accent-dim"
          >
            Start the builder →
          </Link>
        </p>
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


function StatusBadge({ published }: { published: boolean }) {
  return (
    <span
      className={`absolute right-1.5 top-1.5 rounded-full px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-white ${
        published ? "bg-emerald-600/90" : "bg-amber-600/90"
      }`}
    >
      {published ? "published" : "queued"}
    </span>
  );
}


function BallPin({ x_pct, y_pct }: { x_pct: number; y_pct: number }) {
  // Small visual indicator showing where the operator marked the ball,
  // so the queue view doubles as a calibration sanity check.
  return (
    <svg
      className="pointer-events-none absolute h-5 w-5 -translate-x-1/2 -translate-y-1/2"
      style={{ left: `${x_pct}%`, top: `${y_pct}%` }}
      viewBox="-20 -20 40 40"
      aria-hidden
    >
      <circle r="9" fill="none" className="stroke-emerald-300" strokeWidth="2" />
      <circle r="1.5" className="fill-emerald-300" />
    </svg>
  );
}
