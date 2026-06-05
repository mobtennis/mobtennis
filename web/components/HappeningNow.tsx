"use client";

import React from "react";
import Link from "next/link";

import {
  type IndexTournament,
  type MatchSummary,
  type TournamentsIndexResponse,
} from "@/lib/api";
import { MatchCard } from "@/components/MatchCard";
import { MatchFilterBar } from "@/components/MatchFilters";
import { SectionHeader } from "@/components/SectionHeader";
import { SpotTheBallHomeCard } from "@/components/SpotTheBallHomeCard";
import { TournamentCard } from "@/components/TournamentCard";
import { passesFilter } from "@/lib/match-filters";
import { useMatchFilters } from "@/lib/match-filters-client";
import { tierWeight } from "@/lib/tier";

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


function OngoingTournamentBlock({
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
  // No live AND no upcoming-to-show: just the card. Only reachable for
  // big tournaments (the non-big "no live" case bails out earlier).
  if (total === 0) return <TournamentCard t={tournament} />;

  const href = `/tournaments/${tournament.tour}/${tournament.slug}`;

  return (
    <div className="overflow-hidden rounded-lg border border-ink-700 bg-ink-900 shadow-card">
      <Link
        href={href}
        className="flex items-center justify-between border-b border-ink-700 bg-ink-800/60 px-3 py-2 hover:bg-ink-800"
      >
        <span className="truncate text-sm font-semibold">{tournament.name}</span>
        <span className="shrink-0 text-[11px] font-semibold text-text-muted">
          {liveMatches.length > 0
            ? `${liveMatches.length} live`
            : "Upcoming"}
        </span>
      </Link>
      <div className="divide-y divide-ink-700/50">
        {liveMatches.map((m) => (
          <div key={m.id} className="bg-ink-900">
            <MatchCard match={m} />
          </div>
        ))}
        {upcomingMatches.length > 0 && (
          <>
            {/* Subtle band separating live from upcoming so the user
                understands the bottom rows aren't currently in play. */}
            <div className="bg-ink-900/40 px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-text-muted">
              Next up
            </div>
            {upcomingMatches.map((m) => (
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

