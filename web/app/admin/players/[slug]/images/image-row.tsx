"use client";

import { useState, useTransition } from "react";

import { API_BASE, type PlayerImage } from "@/lib/api";

/**
 * One image card in the admin grid. Renders the photo plus
 * Set primary / Hide / Unhide buttons that POST to the admin
 * endpoints. Refreshes the page after each mutation so the new
 * state shows up without needing a manual reload.
 */
export function ImageRow({
  image,
  slug,
  adminKey,
}: {
  image: PlayerImage;
  slug: string;
  adminKey: string;
}) {
  const [pending, start] = useTransition();
  const [err, setErr] = useState<string | null>(null);

  const post = (path: string, params?: Record<string, string>) =>
    start(async () => {
      setErr(null);
      const q = new URLSearchParams({ key: adminKey, ...(params ?? {}) });
      const res = await fetch(
        `${API_BASE}${path}?${q.toString()}`,
        { method: "POST" },
      );
      if (!res.ok) {
        setErr(`${res.status} ${res.statusText}`);
        return;
      }
      // Hard reload — the page is a server component and we just
      // mutated state on the backend. router.refresh() would also
      // work but reload is simpler and admin frequency is low.
      window.location.reload();
    });

  return (
    <div
      className={`overflow-hidden rounded-lg border ${
        image.is_primary
          ? "border-accent"
          : image.is_hidden
            ? "border-ink-700 opacity-40"
            : "border-ink-700"
      } bg-ink-900`}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={image.url}
        alt=""
        className="aspect-[3/4] w-full object-cover"
        loading="lazy"
      />
      <div className="space-y-2 p-2 text-xs">
        <div className="flex flex-wrap items-center gap-1.5 text-[10px] uppercase tracking-wider text-text-muted">
          <span className="rounded bg-ink-800 px-1.5 py-0.5">{image.source}</span>
          {image.is_primary && (
            <span className="rounded bg-accent/20 px-1.5 py-0.5 text-accent">
              primary
            </span>
          )}
          {image.is_hidden && (
            <span className="rounded bg-ink-800 px-1.5 py-0.5">hidden</span>
          )}
        </div>
        {image.credit && (
          <div className="text-text-muted">{image.credit}</div>
        )}
        <div className="flex flex-wrap gap-2 pt-1">
          {!image.is_primary && !image.is_hidden && (
            <button
              type="button"
              disabled={pending}
              onClick={() =>
                post(`/api/admin/players/${slug}/images/${image.id}/primary`)
              }
              className="rounded border border-accent/60 px-2 py-1 text-[11px] font-medium text-accent hover:bg-accent/10 disabled:opacity-50"
            >
              Set primary
            </button>
          )}
          {!image.is_hidden ? (
            <button
              type="button"
              disabled={pending}
              onClick={() =>
                post(
                  `/api/admin/players/${slug}/images/${image.id}/hidden`,
                  { hidden: "true" },
                )
              }
              className="rounded border border-ink-700 px-2 py-1 text-[11px] font-medium text-text-secondary hover:bg-ink-800 disabled:opacity-50"
            >
              Hide
            </button>
          ) : (
            <button
              type="button"
              disabled={pending}
              onClick={() =>
                post(
                  `/api/admin/players/${slug}/images/${image.id}/hidden`,
                  { hidden: "false" },
                )
              }
              className="rounded border border-ink-700 px-2 py-1 text-[11px] font-medium text-text-secondary hover:bg-ink-800 disabled:opacity-50"
            >
              Unhide
            </button>
          )}
          {image.source_url && (
            <a
              href={image.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="ml-auto text-[11px] text-text-muted underline decoration-dotted hover:text-text-secondary"
            >
              source
            </a>
          )}
        </div>
        {err && <div className="text-[11px] text-red-400">{err}</div>}
      </div>
    </div>
  );
}
