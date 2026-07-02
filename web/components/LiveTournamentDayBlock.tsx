"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import type { IndexTournament, MatchSummary } from "@/lib/api";
import { MatchCard } from "@/components/MatchCard";
import { TournamentDayScroller } from "@/components/TournamentDayScroller";
import { passesFilter } from "@/lib/match-filters";
import { useMatchFilters } from "@/lib/match-filters-client";
import {
  defaultSelectedDate,
  groupMatchesByDay,
} from "@/lib/tournament-days";

/**
 * Big-tournament block on the live page. Behaves like a mini
 * tournament view: on mount it lazy-fetches all matches for this
 * tournament and renders a day scroller so the user can look at
 * past-day results and future-day schedules without leaving the
 * home page.
 *
 * Kept as a separate client component so the SSR live payload
 * doesn't need to pull down every match for every slam — the block
 * bootstraps with today's live + upcoming (already provided by the
 * server render) and augments after mount.
 */

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "https://api.mob.tennis";


type Props = {
  tournament: IndexTournament;
  initialLive: MatchSummary[];
  initialUpcoming: MatchSummary[];
  isBig: boolean;
};


function matchesQuery(m: MatchSummary, q: string): boolean {
  if (!q) return true;
  const needle = q.toLowerCase();
  const p1 = m.player1?.full_name?.toLowerCase() ?? "";
  const p2 = m.player2?.full_name?.toLowerCase() ?? "";
  return p1.includes(needle) || p2.includes(needle);
}


export function LiveTournamentDayBlock({
  tournament,
  initialLive,
  initialUpcoming,
  isBig,
}: Props) {
  const [allMatches, setAllMatches] = useState<MatchSummary[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [filterOpen, setFilterOpen] = useState(false);

  // Fetch every match for this tournament on mount. Retry-once on
  // failure so a transient blip doesn't leave the block empty.
  useEffect(() => {
    let cancelled = false;
    async function load(attempt = 0): Promise<void> {
      try {
        const url = `${API_BASE}/api/tournaments/${tournament.tour}/${tournament.slug}/matches?limit=256`;
        const res = await fetch(url);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = (await res.json()) as MatchSummary[];
        if (!cancelled) {
          setAllMatches(data);
          setLoading(false);
        }
      } catch {
        if (attempt === 0 && !cancelled) return load(1);
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [tournament.tour, tournament.slug]);

  // Category filter (men's / women's / singles / doubles) is owned by
  // the top-level MatchFilterBar and shared across the page. Apply it
  // here BEFORE the day grouping so days without any matches for the
  // active filter disappear from the scroller — otherwise chips
  // implied content that wasn't actually shown.
  const { effective } = useMatchFilters();
  const rawMatches = allMatches ?? [...initialLive, ...initialUpcoming];
  const matches = useMemo(
    () => rawMatches.filter((m) => passesFilter(m, effective)),
    [rawMatches, effective],
  );
  const days = useMemo(() => groupMatchesByDay(matches), [matches]);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  // Reset selection whenever the day list changes (initial fetch
  // landing, tournament rotating).
  useEffect(() => {
    setSelectedDate(defaultSelectedDate(days));
  }, [days.length, days.map((d) => d.date).join("|")]);

  const dayMatches = useMemo(() => {
    if (!selectedDate) return matches;
    return matches.filter(
      (m) => m.scheduled_at && m.scheduled_at.slice(0, 10) === selectedDate,
    );
  }, [matches, selectedDate]);

  const [liveInDay, upcomingInDay, finishedInDay] = useMemo(() => {
    const live: MatchSummary[] = [];
    const upcoming: MatchSummary[] = [];
    const finished: MatchSummary[] = [];
    for (const m of dayMatches) {
      if (m.status === "live" || m.status === "suspended") live.push(m);
      else if (m.status === "finished") finished.push(m);
      else if (m.status === "scheduled") upcoming.push(m);
    }
    return [live, upcoming, finished];
  }, [dayMatches]);

  const filteredLive = liveInDay.filter((m) => matchesQuery(m, query));
  const filteredUpcoming = upcomingInDay.filter((m) => matchesQuery(m, query));
  const filteredFinished = finishedInDay.filter((m) => matchesQuery(m, query));
  const filteredTotal =
    filteredLive.length + filteredUpcoming.length + filteredFinished.length;

  const href = `/tournaments/${tournament.tour}/${tournament.slug}`;
  const showFilter = matches.length >= 5;

  // Hide the whole block once we've loaded and the active category
  // filter (women's / men's / singles / doubles) leaves the
  // tournament with zero matches. Prevents e.g. an ATP-only slam
  // still showing an empty scroller when "Women's singles" is on.
  if (!loading && matches.length === 0) return null;

  return (
    <div className="overflow-hidden rounded-lg border border-ink-700 bg-ink-900 shadow-card">
      <div className="flex items-center gap-2 border-b border-ink-700 bg-ink-800/60 px-3 py-2">
        <Link
          href={href}
          className="min-w-0 shrink truncate text-sm font-semibold hover:text-accent"
        >
          {tournament.name}
          {tournament.phase === "qualifying" && (
            <span className="ml-1.5 text-text-muted font-medium">(Qualifying)</span>
          )}
        </Link>
        {showFilter && filterOpen && (
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onBlur={() => { if (!query) setFilterOpen(false); }}
            onKeyDown={(e) => {
              if (e.key === "Escape") { setQuery(""); setFilterOpen(false); }
            }}
            autoFocus
            className="min-w-0 flex-1 border-0 bg-transparent px-1 py-0.5 text-xs text-text-primary focus:outline-none"
          />
        )}
        <span className="shrink-0 text-[11px] font-semibold text-text-muted">
          {loading ? "…" : `${matches.length} matches`}
        </span>
        {showFilter && (
          <button
            type="button"
            onClick={() => setFilterOpen((v) => !v)}
            aria-label="Filter matches by player name"
            className="shrink-0 text-text-muted/70 hover:text-text-secondary"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <circle cx="11" cy="11" r="7" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          </button>
        )}
      </div>

      {days.length > 1 && (
        <div className="border-b border-ink-700 bg-ink-900 px-3 py-2">
          <TournamentDayScroller
            days={days}
            selectedDate={selectedDate}
            onSelect={setSelectedDate}
          />
        </div>
      )}

      <div className="divide-y divide-ink-700/50">
        {filteredLive.length > 0 && (
          <>
            {filteredLive.map((m) => (
              <div key={m.id} className="bg-ink-900"><MatchCard match={m} /></div>
            ))}
          </>
        )}
        {filteredUpcoming.length > 0 && (
          <>
            <div className="bg-ink-900/40 px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-text-muted">
              Scheduled
            </div>
            {filteredUpcoming.map((m) => (
              <div key={m.id} className="bg-ink-900"><MatchCard match={m} /></div>
            ))}
          </>
        )}
        {filteredFinished.length > 0 && (
          <>
            <div className="bg-ink-900/40 px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-text-muted">
              Results
            </div>
            {filteredFinished.map((m) => (
              <div key={m.id} className="bg-ink-900"><MatchCard match={m} /></div>
            ))}
          </>
        )}
        {!loading && filteredTotal === 0 && (
          <div className="px-3 py-4 text-center text-xs text-text-muted">
            {query ? `No matches for "${query}".` : "No matches for this day."}
          </div>
        )}
      </div>

      {isBig && (
        <Link
          href={href}
          className="block border-t border-ink-700 bg-ink-800/30 px-3 py-2 text-center text-[11px] font-semibold text-accent hover:bg-ink-800/60"
        >
          See all matches →
        </Link>
      )}
    </div>
  );
}
