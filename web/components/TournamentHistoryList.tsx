"use client";

import Link from "next/link";
import { useState } from "react";

import { api, type TournamentHistoryEntry } from "@/lib/api";
import { surfaceColor } from "@/lib/format";

type Props = {
  playerSlug: string;
  initial: TournamentHistoryEntry[];
  initialOffset: number; // first chunk is items [0..initial.length)
};

const PAGE_SIZE = 10;

export function TournamentHistoryList({ playerSlug, initial, initialOffset }: Props) {
  const [entries, setEntries] = useState(initial);
  const [offset, setOffset] = useState(initialOffset);
  const [exhausted, setExhausted] = useState(initial.length < initialOffset);
  const [loading, setLoading] = useState(false);

  async function loadMore() {
    setLoading(true);
    try {
      const next = await api<TournamentHistoryEntry[]>(
        `/api/players/${playerSlug}/tournament-history?limit=${PAGE_SIZE}&offset=${offset}`,
      );
      if (next.length === 0) {
        setExhausted(true);
      } else {
        setEntries((prev) => [...prev, ...next]);
        setOffset((o) => o + next.length);
        if (next.length < PAGE_SIZE) setExhausted(true);
      }
    } catch {
      setExhausted(true);
    } finally {
      setLoading(false);
    }
  }

  if (entries.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-ink-700 px-4 py-6 text-center text-sm text-text-muted">
        No completed tournaments yet.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <ul className="overflow-hidden rounded-lg border border-ink-700 bg-ink-900">
        {entries.map((e, i) => (
          <li key={`${e.tournament_slug}-${e.tournament_year}-${e.tournament_tour}`}>
            <Link
              href={`/tournaments/${e.tournament_tour}/${e.tournament_slug}`}
              className={`flex items-center gap-3 px-3 py-2.5 hover:bg-ink-800 ${
                i > 0 ? "border-t border-ink-700" : ""
              }`}
            >
              <ResultBadge result={e.result} isWinner={e.is_winner} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="truncate text-sm font-semibold">{e.tournament_name}</span>
                  <span className="text-[10px] uppercase tracking-wider text-text-muted">
                    {e.tournament_tour}
                  </span>
                </div>
                <div className="mt-0.5 flex items-center gap-2 text-[11px] text-text-muted">
                  <span className="tnum">{e.tournament_year}</span>
                  {e.tournament_surface && (
                    <span className={surfaceColor(e.tournament_surface)}>· {e.tournament_surface}</span>
                  )}
                </div>
              </div>
            </Link>
          </li>
        ))}
      </ul>
      {!exhausted && (
        <button
          type="button"
          onClick={loadMore}
          disabled={loading}
          className="w-full rounded-md border border-ink-700 bg-ink-900 px-3 py-2 text-xs font-semibold text-text-secondary hover:border-ink-600 hover:text-text-primary disabled:opacity-50"
        >
          {loading ? "Loading…" : "Show more"}
        </button>
      )}
    </div>
  );
}

function ResultBadge({ result, isWinner }: { result: string; isWinner: boolean }) {
  // Trophy for wins; pill for everything else. Color-coded by depth so the
  // eye can scan a player's recent form quickly.
  const cls = isWinner
    ? "bg-amber-100 text-amber-800 border-amber-200"
    : result === "F"
      ? "bg-rose-100 text-rose-800 border-rose-200"
      : result === "SF"
        ? "bg-fuchsia-100 text-fuchsia-800 border-fuchsia-200"
        : result === "QF"
          ? "bg-sky-100 text-sky-800 border-sky-200"
          : "bg-ink-800 text-text-secondary border-ink-700";
  return (
    <span
      className={`inline-flex h-7 w-12 shrink-0 items-center justify-center rounded-md border text-[11px] font-bold ${cls}`}
    >
      {isWinner ? "🏆 W" : result}
    </span>
  );
}
