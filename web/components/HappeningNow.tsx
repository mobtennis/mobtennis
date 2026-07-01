"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";

import {
  type IndexTournament,
  type MatchSummary,
  type TournamentsIndexResponse,
} from "@/lib/api";
import { LiveTournamentDayBlock } from "@/components/LiveTournamentDayBlock";
import { MatchCard } from "@/components/MatchCard";
import { MatchFilterBar } from "@/components/MatchFilters";
import { SectionHeader } from "@/components/SectionHeader";
import { SpotTheBallHomeCard } from "@/components/SpotTheBallHomeCard";
import { TournamentCard } from "@/components/TournamentCard";
import { passesFilter } from "@/lib/match-filters";
import { useMatchFilters } from "@/lib/match-filters-client";
import { tierWeight } from "@/lib/tier";
import { DAY_SCROLLER_CATEGORIES } from "@/lib/tournament-days";

// Big-tier categories get the "always show" treatment — they appear on
// the live page even between match sessions or before play has started,
// with up to UPCOMING_PER_BIG next-up cards.
const BIG_TIERS = new Set([
  "grand_slam",
  "atp_1000",
  "wta_1000",
  "atp_finals",
  "wta_finals",
]);
const UPCOMING_PER_BIG = 2;


type Props = {
  liveMatches: MatchSummary[];
  upcomingFeatured: MatchSummary[];
  tIndex: TournamentsIndexResponse;
};

export function HappeningNow({ liveMatches, upcomingFeatured, tIndex }: Props) {
  const { effective } = useMatchFilters();
  const ongoing = tIndex.sections.find((s) => s.key === "live")?.tournaments ?? [];

  if (ongoing.length === 0) {
    return <RecentTournamentsFallback tIndex={tIndex} />;
  }

  // Index live and upcoming by `${tour}/${slug}/${year}` so joint-event
  // cards (Australian Open collapses to one card with `tours: [atp, wta]`)
  // can pull both tours' matches when rendering.
  const liveByKey = groupByTournamentKey(liveMatches);
  const upcomingByKey = groupByTournamentKey(upcomingFeatured);

  const collectForTournament = (
    t: IndexTournament,
    bag: Map<string, MatchSummary[]>,
  ): MatchSummary[] => {
    const tours = t.tours.length > 0 ? t.tours : [t.tour];
    return tours.flatMap((tour) => bag.get(`${tour}/${t.slug}/${t.year}`) ?? []);
  };

  // Build the list of tournament blocks first (some non-big rows
  // return null and we don't want those counted toward "first"),
  // then inject the Spot the Ball card right after the first
  // rendered block. Premium real estate without burying the live
  // tournament that's the headline.
  const renderedBlocks: React.ReactNode[] = [];
  for (const t of ongoing) {
    const isBig = BIG_TIERS.has(t.category);
    const allLive = collectForTournament(t, liveByKey);
    const liveFiltered = allLive.filter((m) => passesFilter(m, effective));

    let upcomingFiltered: MatchSummary[] = [];
    if (isBig) {
      const allUpcoming = collectForTournament(t, upcomingByKey);
      upcomingFiltered = allUpcoming
        .filter((m) => passesFilter(m, effective))
        .slice(0, UPCOMING_PER_BIG);
    }

    if (!isBig && allLive.length > 0 && liveFiltered.length === 0) continue;
    if (!isBig && allLive.length === 0) continue;

    renderedBlocks.push(
      <OngoingTournamentBlock
        key={`${t.tour}/${t.slug}/${t.year}`}
        tournament={t}
        liveMatches={liveFiltered}
        upcomingMatches={upcomingFiltered}
        isBig={isBig}
      />,
    );
  }

  return (
    <section>
      <SectionHeader title="Happening now" />
      <div className="mt-2 space-y-3">
        <MatchFilterBar />
        {renderedBlocks.map((block, i) => (
          <React.Fragment key={i}>
            {block}
            {i === 0 && <SpotTheBallHomeCard />}
          </React.Fragment>
        ))}
        {/* If there are zero rendered tournament blocks (all filtered
            out by the user's pill selection), the game card still
            shows — useful idle-state UX. */}
        {renderedBlocks.length === 0 && <SpotTheBallHomeCard />}
      </div>
    </section>
  );
}


function groupByTournamentKey(matches: MatchSummary[]): Map<string, MatchSummary[]> {
  const out = new Map<string, MatchSummary[]>();
  for (const m of matches) {
    const key = `${m.tournament_tour ?? ""}/${m.tournament_slug}/${m.tournament_year}`;
    if (!out.has(key)) out.set(key, []);
    out.get(key)!.push(m);
  }
  return out;
}


function matchesQuery(m: MatchSummary, q: string): boolean {
  if (!q) return true;
  const needle = q.toLowerCase();
  const p1 = m.player1?.full_name?.toLowerCase() ?? "";
  const p2 = m.player2?.full_name?.toLowerCase() ?? "";
  return p1.includes(needle) || p2.includes(needle);
}


function OngoingTournamentBlock(props: {
  tournament: IndexTournament;
  liveMatches: MatchSummary[];
  upcomingMatches: MatchSummary[];
  isBig: boolean;
}) {
  // Big tournaments (Slams + 500+ + Finals) get a lazy-loaded
  // day-scroller block that spans past + today + future. The simpler
  // today/upcoming layout stays for 250s and below.
  if (DAY_SCROLLER_CATEGORIES.has(props.tournament.category)) {
    return (
      <LiveTournamentDayBlock
        tournament={props.tournament}
        initialLive={props.liveMatches}
        initialUpcoming={props.upcomingMatches}
        isBig={props.isBig}
      />
    );
  }
  return <SmallOngoingTournamentBlock {...props} />;
}


function SmallOngoingTournamentBlock({
  tournament,
  liveMatches,
  upcomingMatches,
  isBig,
}: {
  tournament: IndexTournament;
  liveMatches: MatchSummary[];
  upcomingMatches: MatchSummary[];
  isBig: boolean;
}) {
  const total = liveMatches.length + upcomingMatches.length;
  // Threshold: only show the per-tournament filter once there are
  // enough matches for scrolling to be tedious. Small events like a
  // WTA 250 with 2 live matches don't need it.
  const showFilter = total >= 5;
  const [query, setQuery] = useState("");
  const [filterOpen, setFilterOpen] = useState(false);
  const inputRef = React.useRef<HTMLInputElement | null>(null);

  const filteredLive = useMemo(
    () => (showFilter ? liveMatches.filter((m) => matchesQuery(m, query)) : liveMatches),
    [showFilter, liveMatches, query],
  );
  const filteredUpcoming = useMemo(
    () => (showFilter ? upcomingMatches.filter((m) => matchesQuery(m, query)) : upcomingMatches),
    [showFilter, upcomingMatches, query],
  );
  const filteredTotal = filteredLive.length + filteredUpcoming.length;

  // No live AND no upcoming-to-show: just the card. Only reachable for
  // big tournaments (the non-big "no live" case bails out earlier).
  if (total === 0) return <TournamentCard t={tournament} showPhase />;

  const href = `/tournaments/${tournament.tour}/${tournament.slug}`;

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
            ref={inputRef}
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onBlur={() => { if (!query) setFilterOpen(false); }}
            onKeyDown={(e) => {
              if (e.key === "Escape") {
                setQuery("");
                setFilterOpen(false);
                inputRef.current?.blur();
              }
            }}
            className="min-w-0 flex-1 border-0 bg-transparent px-1 py-0.5 text-xs text-text-primary focus:outline-none"
          />
        )}
        <span className="shrink-0 text-[11px] font-semibold text-text-muted">
          {liveMatches.length > 0
            ? `${liveMatches.length} live`
            : "Upcoming"}
        </span>
        {showFilter && (
          <button
            type="button"
            onClick={() => {
              setFilterOpen((v) => !v);
              // Focus after paint so the input exists in the DOM.
              requestAnimationFrame(() => inputRef.current?.focus());
            }}
            aria-label="Filter matches by player name"
            className="shrink-0 text-text-muted/70 hover:text-text-secondary"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="14" height="14" viewBox="0 0 24 24"
              fill="none" stroke="currentColor"
              strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
              aria-hidden
            >
              <circle cx="11" cy="11" r="7" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          </button>
        )}
      </div>
      {showFilter && filteredTotal === 0 && query && (
        <div className="border-b border-ink-700 bg-ink-900 px-3 py-3 text-center text-xs text-text-muted">
          No matches for "{query}".
        </div>
      )}
      <div className="divide-y divide-ink-700/50">
        {filteredLive.map((m) => (
          <div key={m.id} className="bg-ink-900">
            <MatchCard match={m} />
          </div>
        ))}
        {filteredUpcoming.length > 0 && (
          <>
            {/* Subtle band separating live from upcoming so the user
                understands the bottom rows aren't currently in play. */}
            <div className="bg-ink-900/40 px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-text-muted">
              Next up
            </div>
            {filteredUpcoming.map((m) => (
              <div key={m.id} className="bg-ink-900">
                <MatchCard match={m} />
              </div>
            ))}
          </>
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


// "No ongoing tournaments" fallback — pick the 5 most relevant tournaments
// to surface. Strategy: take the 10 most recently-ended tournaments (by
// end_date desc) across all non-live sections, then re-sort by tier weight
// and slice 5.
function RecentTournamentsFallback({ tIndex }: { tIndex: TournamentsIndexResponse }) {
  const candidates = tIndex.sections
    .filter((s) => s.key !== "live")
    .flatMap((s) => s.tournaments);

  if (candidates.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-ink-700 px-4 py-12 text-center">
        <p className="text-sm text-text-secondary">No tournaments to show yet.</p>
      </div>
    );
  }

  const recent = [...candidates]
    .sort((a, b) => {
      const da = a.end_date ? new Date(a.end_date).getTime() : 0;
      const db = b.end_date ? new Date(b.end_date).getTime() : 0;
      return db - da;
    })
    .slice(0, 10);

  const top5 = recent
    .sort((a, b) => tierWeight(a.category) - tierWeight(b.category))
    .slice(0, 5);

  return (
    <section>
      <SectionHeader title="Recent tournaments" actionHref="/tournaments" />
      <ul className="mt-2 space-y-2">
        {top5.map((t) => (
          <li key={`${t.slug}-${t.year}-${t.tour}`}>
            <TournamentCard t={t} />
          </li>
        ))}
      </ul>
    </section>
  );
}

