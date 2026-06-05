"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { API_BASE } from "@/lib/api";

/**
 * Admin queue / verification page. Shows:
 *  - The pool: calibrated images not yet bundled into a set.
 *    Each shows is_inpainted status — those still pointing at
 *    the Wikimedia source need a Replicate run.
 *  - The published sets: 5-image rounds in publish-date order.
 *    Clicking any image opens its calibrate view.
 */

type PoolImage = {
  id: number;
  set_id: number | null;
  position: number | null;
  image_url: string;
  original_image_url: string | null;
  caption: string;
  is_inpainted: boolean;
  inpaint_attempts: number;
  inpaint_rejected_at: string | null;
  ball_x_pct: number;
  ball_y_pct: number;
};

type SetView = {
  id: number;
  title: string | null;
  publish_date: string;
  images: {
    id: number;
    position: number | null;
    image_url: string;
    caption: string;
    ball_x_pct: number;
    ball_y_pct: number;
  }[];
};

type QueueResponse = {
  pool: PoolImage[];
  sets: SetView[];
};


export function SpotTheBallQueue({ adminKey }: { adminKey: string }) {
  const [data, setData] = useState<QueueResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `${API_BASE}/api/admin/spot-the-ball/queue?key=${encodeURIComponent(adminKey)}`,
      );
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      setData(await res.json());
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [adminKey]);

  useEffect(() => {
    load();
  }, [load]);

  const poolNeedsInpaint = (data?.pool ?? []).filter((p) => !p.is_inpainted).length;
  const poolReadyToBundle = (data?.pool ?? []).filter((p) => p.is_inpainted).length;

  return (
    <div className="space-y-5 p-3">
      <header className="flex items-baseline justify-between gap-3">
        <h1 className="text-xl font-bold tracking-tight">Spot the ball · queue</h1>
        <Link
          href={`/admin/spot-the-ball/builder?key=${encodeURIComponent(adminKey)}`}
          className="text-sm font-medium text-accent hover:text-accent-dim"
        >
          Add more →
        </Link>
      </header>

      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        <Stat label="Pool · needs inpaint" value={poolNeedsInpaint} />
        <Stat label="Pool · ready" value={poolReadyToBundle} />
        <Stat label="Sets" value={data?.sets.length ?? 0} />
        <Stat label="Total pool" value={data?.pool.length ?? 0} />
      </div>

      {poolNeedsInpaint > 0 && (
        <div className="rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-200">
          <p className="font-semibold">{poolNeedsInpaint} image{poolNeedsInpaint > 1 ? "s" : ""} waiting on Replicate.</p>
          <p className="mt-1 text-xs opacity-90">
            Run locally:{" "}
            <code className="rounded bg-black/30 px-1.5 py-0.5">
              REPLICATE_API_TOKEN=… ADMIN_KEY=… python -m
              scripts.process_spot_the_ball_images --queue-only --use-ai
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

      {data && data.pool.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-bold uppercase tracking-wider text-text-muted">Pool</h2>
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {data.pool.map((img) => (
              <li
                key={img.id}
                className={`overflow-hidden rounded-lg border bg-ink-900 ${
                  img.is_inpainted ? "border-emerald-600/30" : "border-amber-600/40"
                }`}
              >
                <Link
                  href={`/admin/spot-the-ball/images/${img.id}?key=${encodeURIComponent(adminKey)}`}
                  className="group block"
                >
                  <div className="relative aspect-video w-full overflow-hidden bg-ink-950">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={img.image_url}
                      alt={img.caption}
                      className="h-full w-full object-cover transition-opacity group-hover:opacity-90"
                      loading="lazy"
                    />
                    <PoolStatusBadge img={img} />
                    <BallPin x_pct={img.ball_x_pct} y_pct={img.ball_y_pct} />
                  </div>
                  <div className="p-2.5">
                    <div className="text-[10px] uppercase tracking-wider text-text-muted">
                      Image #{img.id}
                    </div>
                    <div className="mt-0.5 line-clamp-1 text-sm font-medium text-text-primary">
                      {img.caption}
                    </div>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {data && data.sets.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-bold uppercase tracking-wider text-text-muted">Sets</h2>
          <div className="space-y-3">
            {data.sets.map((s) => (
              <div
                key={s.id}
                className="overflow-hidden rounded-lg border border-ink-700 bg-ink-900 p-3"
              >
                <div className="flex items-baseline justify-between gap-2">
                  <div>
                    <div className="text-[10px] uppercase tracking-wider text-text-muted">
                      {s.publish_date}
                    </div>
                    <div className="text-sm font-medium">{s.title ?? `Round ${s.id}`}</div>
                  </div>
                  <Link
                    href={`/play/spot-the-ball/sets/${s.id}`}
                    className="text-xs font-medium text-accent hover:text-accent-dim"
                  >
                    Preview →
                  </Link>
                </div>
                <ul className="mt-2 grid grid-cols-5 gap-1">
                  {s.images.map((img) => (
                    <li key={img.id}>
                      <Link
                        href={`/admin/spot-the-ball/images/${img.id}?key=${encodeURIComponent(adminKey)}`}
                        className="block aspect-square overflow-hidden rounded border border-ink-700 bg-ink-950"
                      >
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={img.image_url}
                          alt={img.caption}
                          className="h-full w-full object-cover"
                          loading="lazy"
                        />
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </section>
      )}

      {!loading && data && data.pool.length === 0 && data.sets.length === 0 && (
        <p className="text-sm text-text-muted">
          Nothing yet.{" "}
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


function PoolStatusBadge({ img }: { img: PoolImage }) {
  if (img.inpaint_rejected_at) {
    return <Badge tone="red">rejected · retry needed</Badge>;
  }
  if (!img.is_inpainted) {
    return <Badge tone="amber">needs inpaint</Badge>;
  }
  return <Badge tone="emerald">ready</Badge>;
}


function Badge({ tone, children }: { tone: "red" | "amber" | "emerald"; children: React.ReactNode }) {
  const bg =
    tone === "red"
      ? "bg-red-600/90"
      : tone === "amber"
        ? "bg-amber-600/90"
        : "bg-emerald-600/90";
  return (
    <span className={`absolute right-1.5 top-1.5 rounded-full px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-white ${bg}`}>
      {children}
    </span>
  );
}


function BallPin({ x_pct, y_pct }: { x_pct: number; y_pct: number }) {
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
