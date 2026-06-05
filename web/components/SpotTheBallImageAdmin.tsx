"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { API_BASE } from "@/lib/api";

/**
 * Admin view of one SpotTheBallImage. Lets the operator:
 *   - See where the ball is currently calibrated (green pin)
 *   - Click anywhere on the photo to re-calibrate (POSTs to
 *     /calibrate; if the image was already inpainted, the
 *     processor will need to re-run because the click point
 *     moved)
 *   - "Reject inpaint" — marks the current inpaint as bad, restores
 *     the source URL, queues a re-process with a larger mask
 *   - "Remove + skip image" — drops the image entirely and pins the
 *     source to the skip list
 */

type Image = {
  id: number;
  position: number | null;
  image_url: string;
  original_image_url: string | null;
  image_w: number | null;
  image_h: number | null;
  ball_x_pct: number;
  ball_y_pct: number;
  caption: string;
  credit: string | null;
  license_url: string | null;
  source_url: string | null;
};

export function SpotTheBallImageAdmin({
  imageId,
  adminKey,
}: {
  imageId: number;
  adminKey: string;
}) {
  const [img, setImg] = useState<Image | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);
  const router = useRouter();
  const queueHref = `/admin/spot-the-ball/queue?key=${encodeURIComponent(adminKey)}`;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(
        `${API_BASE}/api/admin/spot-the-ball/images/${imageId}?key=${encodeURIComponent(adminKey)}`,
      );
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      setImg(await res.json());
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [imageId, adminKey]);

  useEffect(() => {
    load();
  }, [load]);

  const onImageClick = async (e: React.MouseEvent<HTMLDivElement>) => {
    if (!img) return;
    const el = imgRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const x_pct = ((e.clientX - rect.left) / rect.width) * 100;
    const y_pct = ((e.clientY - rect.top) / rect.height) * 100;
    try {
      const res = await fetch(
        `${API_BASE}/api/admin/spot-the-ball/images/${imageId}/calibrate?key=${encodeURIComponent(adminKey)}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ball_x_pct: x_pct, ball_y_pct: y_pct }),
        },
      );
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      setImg(await res.json());
      setSavedAt(new Date().toLocaleTimeString());
    } catch (e) {
      setError(String(e));
    }
  };

  const onRemove = async () => {
    if (!window.confirm("Remove this image and skip the source permanently?")) return;
    try {
      const res = await fetch(
        `${API_BASE}/api/admin/spot-the-ball/images/${imageId}/remove?key=${encodeURIComponent(adminKey)}`,
        { method: "POST" },
      );
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      router.push(queueHref);
    } catch (e) {
      setError(String(e));
    }
  };

  const onReject = async () => {
    if (!window.confirm("Mark this inpaint as bad? Will re-process on next batch with larger mask.")) return;
    try {
      const res = await fetch(
        `${API_BASE}/api/admin/spot-the-ball/images/${imageId}/reject-inpaint?key=${encodeURIComponent(adminKey)}`,
        { method: "POST" },
      );
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      router.push(queueHref);
    } catch (e) {
      setError(String(e));
    }
  };

  if (loading) return <p className="p-4 text-sm text-text-muted">Loading…</p>;
  if (!img) return <p className="p-4 text-sm text-red-300">{error ?? "Not found"}</p>;

  return (
    <div className="space-y-4 p-3">
      <header className="space-y-1">
        <div className="text-xs uppercase tracking-wider text-text-muted">Image #{img.id}</div>
        <h1 className="text-xl font-bold tracking-tight">{img.caption}</h1>
      </header>

      <div className="rounded-md border border-emerald-500/40 bg-emerald-500/10 p-3 text-sm text-emerald-300">
        Ball at ({img.ball_x_pct.toFixed(1)}%, {img.ball_y_pct.toFixed(1)}%).
        Click anywhere on the photo to re-place; each click saves immediately.
        {savedAt && <span className="ml-2 opacity-70">· last save {savedAt}</span>}
      </div>

      <div
        onClick={onImageClick}
        className="relative w-full select-none overflow-hidden rounded-lg border border-ink-700 bg-ink-900 cursor-crosshair"
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          ref={imgRef}
          src={img.image_url}
          alt={img.caption}
          className="block h-auto w-full"
          draggable={false}
        />
        <Pin x_pct={img.ball_x_pct} y_pct={img.ball_y_pct} />
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Link
          href={queueHref}
          className="rounded-md border border-ink-700 px-3 py-1.5 text-sm font-medium text-text-secondary hover:bg-ink-800"
        >
          ← Back to queue
        </Link>
        <button
          type="button"
          onClick={onReject}
          className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-1.5 text-sm font-medium text-amber-300 hover:bg-amber-500/20"
        >
          Reject inpaint
        </button>
        <button
          type="button"
          onClick={onRemove}
          className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-1.5 text-sm font-medium text-red-300 hover:bg-red-500/20"
        >
          Remove + skip image
        </button>
      </div>

      {error && (
        <div className="rounded-md border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {(img.credit || img.source_url) && (
        <div className="text-[11px] text-text-muted">
          {img.credit && <span>Photo: {img.credit}</span>}
          {img.source_url && (
            <>
              {" · "}
              <a
                href={img.source_url}
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


function Pin({ x_pct, y_pct }: { x_pct: number; y_pct: number }) {
  return (
    <svg
      className="pointer-events-none absolute h-8 w-8 -translate-x-1/2 -translate-y-1/2 drop-shadow-[0_1px_2px_rgba(0,0,0,0.6)]"
      style={{ left: `${x_pct}%`, top: `${y_pct}%` }}
      viewBox="-20 -20 40 40"
      aria-hidden
    >
      <circle r="8" fill="none" className="stroke-emerald-300" strokeWidth="1.4" />
      <line x1="-15" y1="0" x2="-3" y2="0" className="stroke-emerald-300" strokeWidth="1.4" strokeLinecap="round" />
      <line x1="3" y1="0" x2="15" y2="0" className="stroke-emerald-300" strokeWidth="1.4" strokeLinecap="round" />
      <line x1="0" y1="-15" x2="0" y2="-3" className="stroke-emerald-300" strokeWidth="1.4" strokeLinecap="round" />
      <line x1="0" y1="3" x2="0" y2="15" className="stroke-emerald-300" strokeWidth="1.4" strokeLinecap="round" />
      <circle r="1.2" className="fill-emerald-300" />
    </svg>
  );
}
