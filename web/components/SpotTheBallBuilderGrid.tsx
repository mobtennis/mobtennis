"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { API_BASE } from "@/lib/api";

/**
 * Grid-based builder. Replaces the one-image-at-a-time flow.
 *
 *   - Page shows 10 thumbnails at once. Operator scans visually for
 *     "is this a usable Spot the Ball candidate?"
 *   - Click a thumbnail → modal opens with the full image.
 *   - In modal: click the ball to calibrate (POSTs schedule). Or
 *     click "Skip" to remove it from the candidate pool.
 *   - After either action the modal closes and the thumbnail
 *     disappears from the grid.
 *   - When the batch is empty (or whenever the operator wants),
 *     the "Next 10" button refetches.
 *
 * Big speedup over per-image: the operator can reject 8 out of 10
 * with a glance, only opening the modal for the genuine candidates.
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
  pool: number;
  sets_published: number;
  skipped: number;
};

type BatchResponse = {
  candidates: Candidate[];
  stats: Stats;
};

const BATCH_SIZE = 10;


export function SpotTheBallBuilderGrid({ adminKey }: { adminKey: string }) {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Candidate | null>(null);
  // Session-level pagination: every candidate we've shown gets added
  // here. "Next 10" sends this back to the server so we advance
  // through the pool instead of getting the same top-N each time.
  // Resets only on full page reload, which gives the operator a way
  // to start over.
  const [seenIds, setSeenIds] = useState<Set<number>>(new Set());

  const loadBatch = useCallback(async (excludeIds: Set<number>) => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        limit: String(BATCH_SIZE),
        key: adminKey,
      });
      if (excludeIds.size > 0) {
        params.set("exclude", [...excludeIds].join(","));
      }
      const res = await fetch(
        `${API_BASE}/api/admin/spot-the-ball/builder/candidates?${params}`,
      );
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const data: BatchResponse = await res.json();
      setCandidates(data.candidates);
      setStats(data.stats);
      // Mark these as seen so the next "Next 10" advances past them.
      setSeenIds((prev) => {
        const next = new Set(prev);
        for (const c of data.candidates) next.add(c.player_image_id);
        return next;
      });
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [adminKey]);

  const loadFirstBatch = useCallback(() => {
    setSeenIds(new Set());
    loadBatch(new Set());
  }, [loadBatch]);

  const loadNextBatch = useCallback(async () => {
    // Implicit reject: anything visible when the operator clicks
    // "Next 10" is added to the permanent skip list. They've already
    // chosen not to engage with these photos; coming back to them
    // later wastes their time.
    const visibleIds = candidates.map((c) => c.player_image_id);
    if (visibleIds.length > 0) {
      try {
        await fetch(
          `${API_BASE}/api/admin/spot-the-ball/builder/skip-batch?key=${encodeURIComponent(adminKey)}`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ player_image_ids: visibleIds }),
          },
        );
      } catch {
        /* non-fatal: the session-level exclude still hides them
           this round; worst case they reappear next page-reload. */
      }
    }
    loadBatch(seenIds);
  }, [loadBatch, seenIds, candidates, adminKey]);

  useEffect(() => {
    loadFirstBatch();
    // intentionally only on mount; loadFirstBatch identity doesn't matter
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Remove a candidate from the local batch after the operator takes
  // an action on it. Auto-advances when we drain the batch.
  const actioned = useCallback(
    (player_image_id: number) => {
      setCandidates((prev) => {
        const next = prev.filter((c) => c.player_image_id !== player_image_id);
        if (next.length === 0) {
          // Drained the visible batch — auto-load fresh ones,
          // continuing past the IDs we've already shown.
          setTimeout(() => loadBatch(seenIds), 0);
        }
        return next;
      });
      setSelected(null);
    },
    [loadBatch, seenIds],
  );

  return (
    <div className="space-y-4 p-3">
      <header className="flex items-baseline justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-xl font-bold tracking-tight">Spot the ball · builder</h1>
          <p className="text-xs text-text-muted">
            Click a thumbnail to calibrate it; skip the rest. Each
            calibrated image joins the pool for bundling.
          </p>
        </div>
        <Link
          href={`/admin/spot-the-ball/queue?key=${encodeURIComponent(adminKey)}`}
          className="text-sm font-medium text-accent hover:text-accent-dim"
        >
          View queue →
        </Link>
      </header>

      {stats && (
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          <Stat label="Candidates remaining" value={stats.candidates_remaining} />
          <Stat label="Pool" value={stats.pool} />
          <Stat label="Sets published" value={stats.sets_published} />
          <Stat label="Skipped" value={stats.skipped} />
        </div>
      )}

      {error && (
        <div className="rounded-md border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {loading && candidates.length === 0 && (
        <p className="text-sm text-text-muted">Loading…</p>
      )}

      {!loading && candidates.length === 0 && (
        <div className="rounded-md border border-ink-700 bg-ink-900 p-4 text-sm">
          <p className="font-semibold">Pool is empty.</p>
          <p className="mt-1 text-text-secondary">
            All eligible PlayerImages are scheduled or skipped.
          </p>
        </div>
      )}

      {candidates.length > 0 && (
        <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
          {candidates.map((c) => (
            <li key={c.player_image_id}>
              <button
                type="button"
                onClick={() => setSelected(c)}
                className="group relative block aspect-square w-full overflow-hidden rounded-md border border-ink-700 bg-ink-950 transition hover:border-accent"
                title={c.player_name}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={c.image_url}
                  alt={c.player_name}
                  className="h-full w-full object-cover transition-opacity group-hover:opacity-90"
                  loading="lazy"
                />
                <span className="absolute inset-x-0 bottom-0 truncate bg-gradient-to-t from-black/80 to-transparent px-2 py-1 text-[11px] text-white">
                  {c.player_name}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {candidates.length > 0 && (
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={loadNextBatch}
            disabled={loading}
            className="rounded-md border border-ink-700 px-3 py-1.5 text-sm font-medium text-text-secondary hover:bg-ink-800 disabled:opacity-50"
          >
            {loading ? "Loading…" : `Next ${BATCH_SIZE} →`}
          </button>
          <button
            type="button"
            onClick={loadFirstBatch}
            disabled={loading}
            className="rounded-md border border-ink-700 px-3 py-1.5 text-xs font-medium text-text-muted hover:bg-ink-800 disabled:opacity-50"
          >
            Reset
          </button>
          <span className="text-xs text-text-muted">
            (or click a thumb to calibrate it)
          </span>
        </div>
      )}

      {selected && (
        <CalibrateModal
          candidate={selected}
          adminKey={adminKey}
          onClose={() => setSelected(null)}
          onActioned={actioned}
        />
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


function CalibrateModal({
  candidate,
  adminKey,
  onClose,
  onActioned,
}: {
  candidate: Candidate;
  adminKey: string;
  onClose: () => void;
  onActioned: (player_image_id: number) => void;
}) {
  const imgRef = useRef<HTMLImageElement | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Esc + click-outside-image close the modal. Body-scroll lock so
  // the page doesn't drift while a tall image is open.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  const onSkip = async () => {
    if (pending) return;
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
      onActioned(candidate.player_image_id);
    } catch (e) {
      setError(String(e));
    } finally {
      setPending(false);
    }
  };

  const onImageClick = async (e: React.MouseEvent<HTMLImageElement>) => {
    if (pending) return;
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
      onActioned(candidate.player_image_id);
    } catch (err) {
      setError(String(err));
    } finally {
      setPending(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      onClick={onClose}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 p-4"
    >
      <div
        className="relative flex max-h-full max-w-5xl flex-col items-center gap-3"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="text-center text-xs uppercase tracking-wider text-white/70">
          {candidate.player_name}
          {candidate.credit && <> · {candidate.credit}</>}
        </div>

        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          ref={imgRef}
          src={candidate.image_url}
          alt={candidate.player_name}
          className={`max-h-[78vh] max-w-full rounded-md ${
            pending ? "cursor-wait opacity-70" : "cursor-crosshair"
          }`}
          onClick={onImageClick}
          draggable={false}
        />

        <div className="flex flex-wrap items-center justify-center gap-3">
          <button
            type="button"
            onClick={onSkip}
            disabled={pending}
            className="rounded-md border border-red-500/40 bg-red-500/10 px-4 py-2 text-sm font-medium text-red-300 hover:bg-red-500/20 disabled:opacity-50"
          >
            Skip — no good
          </button>
          <button
            type="button"
            onClick={onClose}
            disabled={pending}
            className="rounded-md border border-white/20 px-4 py-2 text-sm text-white/80 hover:bg-white/10 disabled:opacity-50"
          >
            Close
          </button>
          <span className="text-xs text-white/60">
            Click the ball in the photo to calibrate.
          </span>
        </div>

        {error && (
          <div className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-300">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}
