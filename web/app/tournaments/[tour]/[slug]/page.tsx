import { notFound } from "next/navigation";

import {
  api,
  mergeFeed,
  type MatchSummary,
  type NewsItemSummary,
  type TournamentChampion,
  type TournamentDetail,
  type TournamentOverview,
  type Tour,
  type VideoItemSummary,
} from "@/lib/api";
import { AdSlot } from "@/components/AdSlot";
import { LiveStreamRefresh } from "@/components/LiveStreamRefresh";
import { Bracket } from "@/components/Bracket";
import { ChampionsList } from "@/components/ChampionsList";
import { Countdown } from "@/components/Countdown";
import { FilterableMatches } from "@/components/FilterableMatches";
import { TournamentDayPanel } from "@/components/TournamentDayPanel";
import { GetTheAppCard } from "@/components/GetTheAppCard";
import { LastEditionCard } from "@/components/LastEditionCard";
import { MatchFilterBar } from "@/components/MatchFilters";
import { FeedList } from "@/components/FeedList";
import { TrackOnMount } from "@/components/TrackOnMount";
import { EVENTS } from "@/lib/analytics";
import { RecordsList } from "@/components/RecordsList";
import { TournamentOverviewProse } from "@/components/TournamentOverviewProse";
import { SectionHeader } from "@/components/SectionHeader";
import { TourPills } from "@/components/TourPills";
import { TournamentStatsGrid } from "@/components/TournamentStatsGrid";
import { isLocalToday, parseUtcIso, surfaceColor, tournamentColor } from "@/lib/format";
import { scopeForTour, visibleCategoriesForTour } from "@/lib/match-filters";
import { DAY_SCROLLER_CATEGORIES } from "@/lib/tournament-days";

type Params = Promise<{ tour: string; slug: string }>;

function asTour(t: string): Tour | null {
  return t === "atp" || t === "wta" ? t : null;
}

// Disable Vercel's page-level ISR cache. Tournament pages during an
// in-progress event are live data; first-load freshness matters
// (user opens RG tab during a match → wants to see THIS set's score,
// not the score from 60s ago). Backend caches keep load bounded.
export const revalidate = 0;


export async function generateMetadata({ params }: { params: Params }) {
  const { slug, tour } = await params;
  // Pull the resolved edition so the title reflects the actual event
  // name ("French Open 2026") rather than the URL slug ("roland garros").
  // Same endpoint the page body calls — Next.js dedupes the fetch.
  const tournament = await api<TournamentDetail>(
    `/api/tournaments/${tour}/${slug}`,
  ).catch(() => null);
  if (!tournament) {
    return { title: `${slug.replace(/-/g, " ")} (${tour.toUpperCase()})` };
  }
  return {
    title: `${tournament.name} ${tournament.year} (${tour.toUpperCase()})`,
  };
}

export default async function TournamentPage({ params }: { params: Params }) {
  const { tour, slug } = await params;
  const tourEnum = asTour(tour);
  if (!tourEnum) notFound();

  // /api/tournaments/{tour}/{slug} resolves to the most relevant edition
  // (live > in-progress > upcoming > most-recent). The same edition is
  // used for the matches fetch below so they're internally consistent.
  const tournament = await api<TournamentDetail>(
    `/api/tournaments/${tourEnum}/${slug}`,
  ).catch(() => null);
  if (!tournament) notFound();

  const [matches, champions, overview, news, videos] = await Promise.all([
    // revalidate: 0 — let SSE-triggered router.refresh() actually
    // produce fresh data. Backend has a 5-second in-process cache on
    // this endpoint so concurrent visitors don't multiply into N SQL
    // queries; the per-request Next.js fetch cache was redundant AND
    // defeated the SSE-driven refresh by returning cached data inside
    // its 15s window.
    api<MatchSummary[]>(
      `/api/tournaments/${tourEnum}/${slug}/matches?limit=128`,
      { revalidate: 0 },
    ).catch(() => []),
    api<TournamentChampion[]>(
      `/api/tournaments/${tourEnum}/${slug}/champions?limit=5`,
    ).catch(() => []),
    api<TournamentOverview>(
      `/api/tournaments/${tourEnum}/${slug}/overview`,
    ).catch(() => null),
    api<NewsItemSummary[]>(
      `/api/news?tournament_slug=${slug}&limit=8`,
    ).catch(() => []),
    api<VideoItemSummary[]>(
      `/api/videos?tournament_slug=${slug}&limit=8`,
    ).catch(() => []),
  ]);
  const feed = mergeFeed(news, videos);

  // "Today" = currently live/suspended + anything that finished today
  // in the user's local time. Keeping completed matches around for the
  // rest of their day means users don't have to dig into the bracket
  // to see a match that ended an hour ago.
  const live = matches.filter(
    (m) =>
      m.status === "live" ||
      m.status === "suspended" ||
      (m.status === "finished" && isLocalToday(m.scheduled_at)),
  );
  const upcomingCutoff = Date.now() - 30 * 60 * 1000;
  const upcoming = matches.filter(
    (m) =>
      m.status === "scheduled" &&
      (!m.scheduled_at || parseUtcIso(m.scheduled_at).getTime() > upcomingCutoff),
  );
  const isPastEdition = live.length === 0 && upcoming.length === 0;

  const startMs = tournament.start_date
    ? parseUtcIso(tournament.start_date).getTime()
    : null;
  // A tournament can't be "future" while it has live or scheduled
  // matches loaded — even if the stored start_date is in the future.
  // Wimbledon 2026 was hitting this: start_date=2026-06-30 from
  // Wikipedia (the traditional Monday Day 1) but R128 matches were
  // already on the schedule for Sunday 06-29. The Countdown widget
  // saying "starts tomorrow" while the bracket page already showed
  // live R128 results was obvious cognitive dissonance.
  const hasLoadedSchedule = live.length > 0 || upcoming.length > 0;
  const isFutureEdition =
    !hasLoadedSchedule && (
      startMs !== null
        ? startMs > Date.now()
        : tournament.year > new Date().getFullYear()
    );

  const mainDrawMatches = matches.filter(
    (m) =>
      !m.is_doubles &&
      m.round &&
      !["Q", "Q1", "Q2", "Q3"].includes(m.round.toUpperCase()),
  );
  const showBracket = mainDrawMatches.length >= 8;

  // Don't show "Last edition" when the resolved current edition is
  // *already* the most recent finished one (overview.last_edition).
  const showLastEdition =
    overview?.last_edition && overview.last_edition.year !== tournament.year;

  return (
    <div className="space-y-6">
      {/* SSE-driven refresh, always on. Replaces the previous gated
          15s polling timer — that timer turned itself off whenever
          the visible "live" set went empty (between sessions or
          after the last match of the day) and never came back without
          a full reload, leaving users staring at hour-old data on
          tabs they'd kept open. */}
      <LiveStreamRefresh />
      <TrackOnMount
        event={EVENTS.tournamentOpened}
        properties={{
          slug: tournament.slug,
          tour: tournament.tour,
          year: tournament.year,
          category: tournament.category,
        }}
      />

      <TournamentHero tournament={tournament} isFuture={isFutureEdition} />

      <GetTheAppCard action={`follow ${tournament.name}`} variant="card" />

      {/* Editorial overview — templated prose anchored on our records +
          stats, with a Wikipedia "further reading" link at the end.
          Replaces the previous setup where the raw Wikipedia description
          ran here AND the templated paragraph appeared lower; that
          read as two competing intros. */}
      <TournamentOverviewProse tournament={tournament} overview={overview} />

      {isFutureEdition && tournament.start_date && (
        <Countdown targetDate={tournament.start_date} />
      )}

      {overview?.stats && <TournamentStatsGrid stats={overview.stats} />}

      <AdSlot slot="tournament-mid" />

      {(live.length > 0 || upcoming.length > 0) && (
        <MatchFilterBar
          visible={visibleCategoriesForTour(tourEnum)}
          scope={scopeForTour(tourEnum)}
        />
      )}

      {DAY_SCROLLER_CATEGORIES.has(tournament.category) ? (
        // Big tournaments (500+ / Slams / Finals) get a day scroller
        // driving a single filtered list — covers past + today + future
        // in one control instead of a today / upcoming split. Doubles /
        // singles pruning is handled downstream by FilterableMatches
        // via the shared MatchFilterBar cookies.
        matches.length > 0 && (
          <TournamentDayPanel
            matches={matches}
            year={tournament.year}
            visible={visibleCategoriesForTour(tourEnum)}
            scope={scopeForTour(tourEnum)}
          />
        )
      ) : (
        <>
          {live.length > 0 && (
            <FilterableMatches
              title={`Today · ${tournament.year}`}
              matches={live}
              visible={visibleCategoriesForTour(tourEnum)}
              scope={scopeForTour(tourEnum)}
            />
          )}
          {upcoming.length > 0 && (
            <FilterableMatches
              title={`Upcoming · ${tournament.year}`}
              matches={upcoming.slice(0, 30)}
              visible={visibleCategoriesForTour(tourEnum)}
              scope={scopeForTour(tourEnum)}
            />
          )}
        </>
      )}

      {/* Standalone bracket only renders for an in-progress edition.
          Past editions surface their bracket through the expandable
          rows in ChampionsList below. */}
      {showBracket && !isPastEdition && (
        <section>
          <SectionHeader title={`Bracket · ${tournament.year}`} />
          <div className="mt-2">
            <Bracket
              matches={mainDrawMatches}
              drawSize={tournament.draw_size}
              padPlaceholders={true}
            />
          </div>
        </section>
      )}

      {showLastEdition && overview?.last_edition && (
        <section>
          <SectionHeader
            title="Last edition"
            subtitle={`How the ${overview.last_edition.year} edition ended`}
          />
          <div className="mt-2">
            <LastEditionCard edition={overview.last_edition} />
          </div>
        </section>
      )}

      {champions.length > 0 && (
        <section>
          <SectionHeader title="Past champions" subtitle="Most recent first" />
          <div className="mt-2">
            <ChampionsList
              tour={tourEnum}
              slug={slug}
              initial={champions}
              initialOffset={champions.length}
            />
          </div>
        </section>
      )}

      {overview && overview.records.length > 0 && (
        <section>
          <SectionHeader title="Records" />
          <div className="mt-2"><RecordsList records={overview.records} /></div>
        </section>
      )}

      {feed.length > 0 && (
        <section>
          <SectionHeader title="News & highlights" />
          <div className="mt-2"><FeedList items={feed} /></div>
        </section>
      )}

      {matches.length === 0 && (
        <EmptyEditionNote
          isFuture={isFutureEdition}
          year={tournament.year}
          hasLastEdition={Boolean(overview?.last_edition)}
        />
      )}
    </div>
  );
}


function EmptyEditionNote({
  isFuture,
  year,
  hasLastEdition,
}: {
  isFuture: boolean;
  year: number;
  hasLastEdition: boolean;
}) {
  if (isFuture) {
    return (
      <div className="rounded-lg border border-dashed border-ink-700 px-4 py-6 text-center text-sm text-text-muted">
        <p className="font-medium text-text-secondary">
          The {year} edition hasn't started yet.
        </p>
        <p className="mt-1 text-xs">
          The schedule will populate closer to the start date.
        </p>
      </div>
    );
  }
  return (
    <div className="rounded-lg border border-dashed border-ink-700 px-4 py-6 text-center text-sm text-text-muted">
      <p className="font-medium text-text-secondary">
        We don't have detailed results for the {year} edition.
      </p>
      <p className="mt-1 text-xs">
        {hasLastEdition
          ? "See the last edition above for the most recent results we do have."
          : "Coverage of past editions of this event is limited."}
      </p>
    </div>
  );
}


function TournamentHero({
  tournament,
  isFuture,
}: {
  tournament: TournamentDetail;
  isFuture: boolean;
}) {
  return (
    <header className="overflow-hidden rounded-lg border border-ink-700 bg-ink-900 shadow-card">
      {tournament.image_url && (
        // These images are brand logos (Wikipedia infobox marks), not
        // photos — so contain them on a soft panel rather than
        // cover-cropping into a banner (which sliced the US Open logo in
        // half). Whole mark, centered, never cropped.
        <div className="flex items-center justify-center border-b border-ink-700 bg-ink-800/40 px-6 py-8">
          <div
            className="h-24 w-full max-w-md bg-contain bg-center bg-no-repeat"
            style={{ backgroundImage: `url(${tournament.image_url})` }}
            role="img"
            aria-label={`${tournament.name} logo`}
          />
        </div>
      )}
      <div className="p-4">
        <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${tournamentColor(tournament.category)}`}>
          {tournament.category.replace(/_/g, " ")}
        </span>
        <h1 className="mt-2 text-2xl font-bold tracking-tight">{tournament.name}</h1>
        <div className="mt-1 flex items-center gap-3 text-xs text-text-secondary">
          {tournament.available_tours.length > 1 ? (
            <TourPills
              active={tournament.tour}
              available={tournament.available_tours}
              slug={tournament.slug}
            />
          ) : (
            <span className="rounded-full bg-ink-800 px-2 py-0.5 font-bold uppercase tracking-wider">
              {tournament.tour.toUpperCase()}
            </span>
          )}
          {tournament.surface && (
            <span className={`font-bold uppercase tracking-wider ${surfaceColor(tournament.surface)}`}>
              {tournament.surface}
            </span>
          )}
          {tournament.city && <span>· {tournament.city}</span>}
          {/* When the resolved edition is upcoming, show a subtle hint of
              the year on the hero so the user knows what they're looking
              at. Otherwise the page is intentionally year-agnostic. */}
          {isFuture && (
            <span className="text-text-muted">· {tournament.year}</span>
          )}
        </div>
      </div>
    </header>
  );
}
