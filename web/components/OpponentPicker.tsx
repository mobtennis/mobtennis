"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { api, type SearchHit } from "@/lib/api";

/**
 * Inline picker used on the H2H page in two situations:
 *   1. Bare half-formed URL (`/h2h/alcaraz-vs-`) — the picker takes
 *      the second player's slot directly, replacing the avatar.
 *   2. A swap link next to player 2 ("Change opponent") — pops a
 *      small inline search field over the page.
 *
 * Picking a player navigates to `/h2h/anchor-vs-newSlug`. Anchor is
 * always the player who's already on the page; we keep them as
 * player 1 so the previously-selected match data is what gets
 * replaced, not the user's mental anchor.
 */
export function OpponentPicker({
  anchorSlug,
  tourFilter,
  compact = false,
  autoFocus = true,
  onCancel,
  placeholder = "Search opponent…",
}: {
  /** Slug we're picking the opponent FOR — becomes player 1 in the new URL. */
  anchorSlug: string;
  /** Restrict results to one tour (the anchor's). ATP plays ATP, WTA
   * plays WTA — showing the opposite tour leads to confusing zero-H2H
   * results. Pass nothing to skip the filter. */
  tourFilter?: string | null;
  /** Smaller variant for the "change opponent" link case. */
  compact?: boolean;
  autoFocus?: boolean;
  /** Optional escape hatch from the compact variant. */
  onCancel?: () => void;
  placeholder?: string;
}) {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (autoFocus) inputRef.current?.focus();
  }, [autoFocus]);

  useEffect(() => {
    if (q.trim().length < 2) {
      setHits([]);
      return;
    }
    setLoading(true);
    const t = setTimeout(() => {
      // Ask for a slightly larger page than we'll show — the tour
      // filter trims results, so a 5-result-on-screen target needs
      // headroom when only half the hits match the anchor's tour.
      api<SearchHit[]>(`/api/search?q=${encodeURIComponent(q)}&limit=20`)
        .then((all) =>
          setHits(
            all
              .filter((h) => h.kind === "player" && h.slug !== anchorSlug)
              .filter((h) => !tourFilter || h.tour === tourFilter)
              .slice(0, 10),
          ),
        )
        .catch(() => setHits([]))
        .finally(() => setLoading(false));
    }, 180);
    return () => clearTimeout(t);
  }, [q, anchorSlug, tourFilter]);

  return (
    <div className={compact ? "w-full" : "flex w-full flex-col items-center gap-2"}>
      <div className="flex w-full items-center gap-2 rounded-full border border-ink-700 bg-ink-900 px-3 py-1.5">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-text-muted">
          <circle cx="11" cy="11" r="7" />
          <path d="M21 21l-4.3-4.3" />
        </svg>
        <input
          ref={inputRef}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape" && onCancel) onCancel();
          }}
          placeholder={placeholder}
          className="flex-1 bg-transparent text-xs outline-none placeholder:text-text-muted"
        />
        {loading && <span className="text-[10px] text-text-muted">…</span>}
      </div>
      {hits.length > 0 && (
        <ul className="w-full overflow-hidden rounded-md border border-ink-700 bg-ink-900 text-left">
          {hits.map((h) => (
            <li key={h.slug}>
              <button
                type="button"
                onClick={() => router.push(`/h2h/${anchorSlug}-vs-${h.slug}`)}
                className="block w-full px-3 py-2 text-xs hover:bg-ink-800"
              >
                <span className="font-medium">{h.name}</span>
                {h.rank != null && (
                  <span className="ml-2 text-[10px] text-text-muted">#{h.rank}</span>
                )}
                <span className="ml-2 text-[10px] uppercase text-text-muted">{h.tour}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
