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
import { AutoRefresh } from "@/components/AutoRefresh";
import { Bracket } from "@/components/Bracket";
import { ChampionsList } from "@/components/ChampionsList";
import { Countdown } from "@/components/Countdown";
import { FilterableMatches } from "@/components/FilterableMatches";
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

type Params = Promise<{ tour: string; slug: string }>;

function asTour(t: string): Tour | null {
  return t === "atp" || t === "wta" ? t : null;
}

export async function generateMetadata({ params }: { params: Params }) {
  const { slug, tour } = await params;
  // Year deliberately omitted — the URL is year-less by design, the page
  // can show any edition's data depending on what's most relevant.
  return { title: `${slug.replace(/-/g, " ")} (${tour.toUpperCase()})` };
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
    // 15s revalidate. Combined with the SSE-driven router.refresh()
    // this still surfaces score updates within ~15s of upstream
    // (the SSE event triggers the refresh; the data cache returns
    // fresh content on the next 15s tick). Anything tighter and the
    // backend gets DDoS'd by routine page revalidations.
    api<MatchSummary[]>(
      `/api/tournaments/${tourEnum}/${slug}/matches?limit=128`,
      { revalidate: 15 },
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
  const isFutureEdition =
    startMs !== null
      ? startMs > Date.now()
      : tournament.year > new Date().getFullYear();

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
      <AutoRefresh enabled={live.some((m) => m.status === "live" || m.status === "suspended")} intervalMs={15_000} />
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

      {tournament.description && (
        <section className="rounded-lg border border-ink-700 bg-ink-900 p-4 shadow-card">
          <p className="text-sm leading-relaxed text-text-secondary">{tournament.description}</p>
          {tournament.wikipedia_url && (
            <a
              href={tournament.wikipedia_url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 inline-block text-xs font-medium text-accent hover:text-accent-dim"
            >
              Read more on Wikipedia →
            </a>
          )}
        </section>
      )}

      {isFutureEdition && tournament.start_date && (
        <Countdown targetDate={tournament.start_date} />
      )}

      {overview?.stats && <TournamentStatsGrid stats={overview.stats} />}

      <TournamentOverviewProse tournament={tournament} overview={overview} />

      <AdSlot slot="tournament-mid" />

      {(live.length > 0 || upcoming.length > 0) && (
        <MatchFilterBar
          visible={visibleCategoriesForTour(tourEnum)}
          scope={scopeForTour(tourEnum)}
        />
      )}

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
    <header className="relative overflow-hidden rounded-lg border border-ink-700 bg-ink-900 shadow-card">
      {tournament.image_url && (
        <>
          <div
            className="h-44 bg-cover bg-center"
            style={{ backgroundImage: `url(${tournament.image_url})` }}
            aria-hidden
          />
          <div className="absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t from-ink-900 via-ink-900/70 to-transparent" />
        </>
      )}
      <div className={tournament.image_url ? "relative -mt-10 p-4" : "p-4"}>
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
