"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { api, type SearchHit } from "@/lib/api";

export default function SearchPage() {
  const params = useSearchParams();
  // ?h2h=<slug> turns this into a "pick the opponent" picker. The
  // first player is the URL slug; clicking a player here builds the
  // full /h2h/p1-vs-p2 URL. This replaces the previous flow that
  // sent users to /h2h/<slug>-vs- (no second player) — which produced
  // an empty-slug request the backend couldn't fast-fail on, which
  // crawlers then hammered into a request pile-up.
  const h2hAnchor = params.get("h2h");
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (q.trim().length < 2) {
      setHits([]);
      return;
    }
    setLoading(true);
    const t = setTimeout(() => {
      api<SearchHit[]>(`/api/search?q=${encodeURIComponent(q)}&limit=20`)
        .then(setHits)
        .catch(() => setHits([]))
        .finally(() => setLoading(false));
    }, 180);
    return () => clearTimeout(t);
  }, [q]);

  // Players only when picking an H2H opponent; otherwise show everything.
  const visibleHits = h2hAnchor ? hits.filter((h) => h.kind === "player") : hits;
  const placeholder = h2hAnchor
    ? "Pick an opponent…"
    : "Search players or tournaments…";

  const linkFor = (h: SearchHit): string => {
    if (h2hAnchor && h.kind === "player") {
      return `/h2h/${h2hAnchor}-vs-${h.slug}`;
    }
    return h.kind === "player"
      ? `/players/${h.slug}`
      : `/tournaments/${h.tour ?? "atp"}/${h.slug}`;
  };

  return (
    <div className="space-y-3">
      {h2hAnchor && (
        <p className="rounded-md border border-ink-700 bg-ink-900 px-3 py-2 text-xs text-text-secondary">
          Pick an opponent for <span className="font-medium text-text-primary">{h2hAnchor.replace(/-/g, " ")}</span>.
        </p>
      )}
      <div className="flex items-center gap-2 rounded-full border border-ink-700 bg-ink-900 px-4 py-2.5">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-text-muted">
          <circle cx="11" cy="11" r="7" />
          <path d="M21 21l-4.3-4.3" />
        </svg>
        <input
          autoFocus
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={placeholder}
          className="flex-1 bg-transparent text-sm outline-none placeholder:text-text-muted"
        />
        {loading && <span className="text-xs text-text-muted">…</span>}
      </div>

      <ul className="divide-y divide-ink-700/50 overflow-hidden rounded-lg border border-ink-700 bg-ink-900">
        {visibleHits.map((h) => (
          <li key={`${h.kind}-${h.slug}-${h.year ?? ""}`}>
            <Link
              href={linkFor(h)}
              className="flex items-center gap-3 px-3 py-3 hover:bg-ink-800"
            >
              <span className={`inline-flex h-6 items-center rounded-full px-2 text-[10px] font-bold uppercase tracking-wider ${h.kind === "player" ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}`}>
                {h.kind}
              </span>
              <span className="flex-1 truncate text-sm font-medium">{h.name}</span>
              {h.rank && <span className="text-xs text-text-muted">#{h.rank}</span>}
              {h.year && <span className="text-xs text-text-muted">{h.year}</span>}
              <span className="text-[10px] uppercase text-text-muted">{h.tour}</span>
            </Link>
          </li>
        ))}
        {q.trim().length >= 2 && !loading && visibleHits.length === 0 && (
          <li className="px-4 py-6 text-center text-sm text-text-muted">No matches.</li>
        )}
      </ul>
    </div>
  );
}
