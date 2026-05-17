"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api, type SearchHit } from "@/lib/api";

export default function SearchPage() {
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

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 rounded-full border border-ink-700 bg-ink-900 px-4 py-2.5">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-text-muted">
          <circle cx="11" cy="11" r="7" />
          <path d="M21 21l-4.3-4.3" />
        </svg>
        <input
          autoFocus
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search players or tournaments…"
          className="flex-1 bg-transparent text-sm outline-none placeholder:text-text-muted"
        />
        {loading && <span className="text-xs text-text-muted">…</span>}
      </div>

      <ul className="divide-y divide-ink-700/50 overflow-hidden rounded-lg border border-ink-700 bg-ink-900">
        {hits.map((h) => (
          <li key={`${h.kind}-${h.slug}-${h.year ?? ""}`}>
            <Link
              href={
                h.kind === "player"
                  ? `/players/${h.slug}`
                  : `/tournaments/${h.tour ?? "atp"}/${h.slug}`
              }
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
        {q.trim().length >= 2 && !loading && hits.length === 0 && (
          <li className="px-4 py-6 text-center text-sm text-text-muted">No matches.</li>
        )}
      </ul>
    </div>
  );
}
