"use client";

import { useEffect, useState } from "react";

import {
  api,
  type MatchSummary,
  type TournamentChampion,
  type Tour,
} from "@/lib/api";
import { BracketGrid } from "@/components/Bracket";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PlayerHoverCard } from "@/components/PlayerHoverCard";

type Props = {
  tour: Tour;
  slug: string;
  initial: TournamentChampion[];
  initialOffset: number;
};

const PAGE_SIZE = 5;

export function ChampionsList({ tour, slug, initial, initialOffset }: Props) {
  const [entries, setEntries] = useState(initial);
  const [offset, setOffset] = useState(initialOffset);
  const [exhausted, setExhausted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [openYear, setOpenYear] = useState<number | null>(null);

  async function loadMore() {
    setLoading(true);
    try {
      const next = await api<TournamentChampion[]>(
        `/api/tournaments/${tour}/${slug}/champions?limit=${PAGE_SIZE}&offset=${offset}`,
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
        No past finals on record.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <ul className="overflow-hidden rounded-lg border border-ink-700 bg-ink-900">
        {entries.map((c, i) => {
          const isOpen = openYear === c.year;
          return (
            <li key={c.year} className={i > 0 ? "border-t border-ink-700" : ""}>
              <button
                type="button"
                onClick={() => setOpenYear(isOpen ? null : c.year)}
                className="flex w-full items-center gap-3 px-3 py-2.5 text-left hover:bg-ink-800"
                aria-expanded={isOpen}
              >
                <span className="w-12 shrink-0 text-center text-sm font-bold tnum text-text-secondary">
                  {c.year}
                </span>
                <PlayerAvatar
                  name={c.champion.full_name}
                  imageUrl={c.champion.image_url}
                  countryCode={c.champion.country_code}
                />
                <span className="min-w-0 flex-1 truncate text-sm font-semibold">
                  <PlayerHoverCard slug={c.champion.slug}>{c.champion.full_name}</PlayerHoverCard>
                </span>
                <span className="shrink-0 text-base">🏆</span>
                <Chevron open={isOpen} />
              </button>
              {isOpen && (
                <div className="border-t border-ink-700 bg-ink-950/40 p-3">
                  <ChampionBracket tour={tour} slug={slug} year={c.year} />
                </div>
              )}
            </li>
          );
        })}
      </ul>
      {!exhausted && (
        <button
          type="button"
          onClick={loadMore}
          disabled={loading}
          className="w-full rounded-md border border-ink-700 bg-ink-900 px-3 py-2 text-xs font-semibold text-text-secondary hover:border-ink-600 hover:text-text-primary disabled:opacity-50"
        >
          {loading ? "Loading…" : "Show earlier years"}
        </button>
      )}
    </div>
  );
}

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      width={14}
      height={14}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`shrink-0 text-text-muted transition-transform ${open ? "rotate-180" : ""}`}
      aria-hidden
    >
      <path d="M6 9l6 6 6-6" />
    </svg>
  );
}

// Lazy-fetch the bracket for this year on first expand. The parent unmounts
// this component on collapse, so re-expanding refetches — fine, the endpoint
// is cheap and we avoid stale data.
function ChampionBracket({ tour, slug, year }: { tour: Tour; slug: string; year: number }) {
  const [state, setState] = useState<
    { kind: "loading" } | { kind: "ready"; matches: MatchSummary[] } | { kind: "error" }
  >({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    api<MatchSummary[]>(`/api/tournaments/${tour}/${slug}/${year}/matches?limit=128`)
      .then((matches) => {
        if (!cancelled) setState({ kind: "ready", matches });
      })
      .catch(() => {
        if (!cancelled) setState({ kind: "error" });
      });
    return () => {
      cancelled = true;
    };
  }, [tour, slug, year]);

  if (state.kind === "loading") {
    return <div className="py-2 text-center text-xs text-text-muted">Loading bracket…</div>;
  }
  if (state.kind === "error") {
    return <div className="py-2 text-center text-xs text-text-muted">Couldn't load.</div>;
  }
  const mainDraw = state.matches.filter(
    (m) => m.round && !["Q", "Q1", "Q2", "Q3"].includes(m.round.toUpperCase()),
  );
  if (mainDraw.length === 0) {
    return <div className="py-2 text-center text-xs text-text-muted">No bracket data.</div>;
  }
  return <BracketGrid matches={mainDraw} drawSize={null} padPlaceholders={false} />;
}
