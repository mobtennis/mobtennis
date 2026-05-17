import { useQuery } from "@tanstack/react-query";
import { Stack, useLocalSearchParams } from "expo-router";
import { Image, Linking, Pressable, Text, View } from "react-native";

import { AdSlot } from "@/components/AdSlot";
import { Bracket } from "@/components/Bracket";
import { ChampionsList } from "@/components/ChampionsList";
import { Countdown } from "@/components/Countdown";
import { FollowButton } from "@/components/FollowButton";
import { LastEditionCard } from "@/components/LastEditionCard";
import { MatchFilterBar } from "@/components/MatchFilters";
import { FeedList } from "@/components/FeedList";
import { RecordsList } from "@/components/RecordsList";
import { Screen } from "@/components/Screen";
import { SectionHeader } from "@/components/SectionHeader";
import { TourPills } from "@/components/TourPills";
import { TournamentGroups } from "@/components/TournamentGroup";
import { TournamentStatsGrid } from "@/components/TournamentStatsGrid";
import {
  api,
  mergeFeed,
  type MatchSummary,
  type NewsItemSummary,
  type Tour,
  type TournamentChampion,
  type TournamentDetail,
  type TournamentOverview,
  type VideoItemSummary,
} from "@/lib/api";
import { isLocalToday, parseUtcIso, surfaceColor } from "@/lib/format";
import { passesFilter, scopeForTour, useMatchFilters, visibleCategoriesForTour } from "@/lib/match-filters";

const CATEGORY_BADGE: Record<string, { bg: string; fg: string }> = {
  grand_slam: { bg: "bg-amber-100", fg: "text-amber-800" },
  atp_1000: { bg: "bg-rose-100", fg: "text-rose-800" },
  wta_1000: { bg: "bg-rose-100", fg: "text-rose-800" },
  atp_500: { bg: "bg-sky-100", fg: "text-sky-800" },
  wta_500: { bg: "bg-sky-100", fg: "text-sky-800" },
  atp_250: { bg: "bg-emerald-100", fg: "text-emerald-800" },
  wta_250: { bg: "bg-emerald-100", fg: "text-emerald-800" },
};

export default function TournamentScreen() {
  const { tour, slug } = useLocalSearchParams<{ tour: string; slug: string }>();
  const validTour = tour === "atp" || tour === "wta";
  const visibleCats = visibleCategoriesForTour(validTour ? (tour as Tour) : null);
  const filterScope = scopeForTour(validTour ? (tour as Tour) : null);
  const { effective } = useMatchFilters({ visible: visibleCats, scope: filterScope });

  // Year-less endpoints: the backend resolves to the most relevant
  // edition (live > in-progress > upcoming > most-recent).
  const { data: tournament, refetch, isRefetching } = useQuery({
    queryKey: ["tournament", tour, slug],
    enabled: !!slug && validTour,
    queryFn: () => api<TournamentDetail>(`/api/tournaments/${tour}/${slug}`),
  });
  const { data: matches = [] } = useQuery({
    queryKey: ["tournament-matches", tour, slug],
    enabled: !!slug && validTour,
    queryFn: () =>
      api<MatchSummary[]>(`/api/tournaments/${tour}/${slug}/matches?limit=128`),
    refetchInterval: 90_000,
  });
  const { data: champions = [] } = useQuery({
    queryKey: ["tournament-champions", tour, slug],
    enabled: !!slug && validTour,
    queryFn: () => api<TournamentChampion[]>(`/api/tournaments/${tour}/${slug}/champions?limit=5`),
    staleTime: 60 * 60_000,
  });
  const { data: overview } = useQuery({
    queryKey: ["tournament-overview", tour, slug],
    enabled: !!slug && validTour,
    queryFn: () => api<TournamentOverview>(`/api/tournaments/${tour}/${slug}/overview`),
    staleTime: 60 * 60_000,
  });
  const { data: news = [] } = useQuery({
    queryKey: ["tournament-news", slug],
    enabled: !!slug,
    queryFn: () => api<NewsItemSummary[]>(`/api/news?tournament_slug=${slug}&limit=8`),
  });
  const { data: videos = [] } = useQuery({
    queryKey: ["tournament-videos", slug],
    enabled: !!slug,
    queryFn: () => api<VideoItemSummary[]>(`/api/videos?tournament_slug=${slug}&limit=8`),
  });

  if (!tournament) {
    return (
      <Screen>
        <Text className="text-center text-text-muted">Loading…</Text>
      </Screen>
    );
  }

  // "Today" = live/suspended + matches that finished today in user's
  // local time. Keeps just-completed matches visible until end of day
  // so users don't have to dig into the bracket to find them.
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
  const liveFiltered = live.filter((m) => passesFilter(m, effective));
  const upcomingFiltered = upcoming.filter((m) => passesFilter(m, effective));
  const mainDrawMatches = matches.filter(
    (m) =>
      !m.is_doubles &&
      m.round &&
      !["Q", "Q1", "Q2", "Q3"].includes(m.round.toUpperCase()),
  );
  const showBracket = mainDrawMatches.length >= 8;
  const badge = CATEGORY_BADGE[tournament.category];
  const showLastEdition =
    overview?.last_edition && overview.last_edition.year !== tournament.year;

  return (
    <Screen onRefresh={refetch} refreshing={isRefetching}>
      <Stack.Screen options={{ title: tournament.name }} />

      <View className="overflow-hidden rounded-lg border border-ink-700 bg-ink-900">
        {tournament.image_url && (
          <Image source={{ uri: tournament.image_url }} style={{ width: "100%", height: 180 }} />
        )}
        <View className={`p-4 ${tournament.image_url ? "-mt-10" : ""}`}>
          {badge && (
            <View className={`self-start rounded-full px-2 py-0.5 ${badge.bg}`}>
              <Text className={`text-[10px] font-bold uppercase tracking-wider ${badge.fg}`}>
                {tournament.category.replace(/_/g, " ")}
              </Text>
            </View>
          )}
          <Text className="mt-2 text-2xl font-bold text-text-primary">{tournament.name}</Text>
          <View className="mt-1 flex-row items-center gap-3">
            {tournament.available_tours.length > 1 ? (
              <TourPills
                active={tournament.tour}
                available={tournament.available_tours}
                slug={tournament.slug}
              />
            ) : (
              <View className="rounded-full bg-ink-800 px-2 py-0.5">
                <Text className="text-[10px] font-bold uppercase tracking-wider text-text-primary">
                  {tournament.tour.toUpperCase()}
                </Text>
              </View>
            )}
            {tournament.surface && (
              <Text
                className={`text-[10px] font-bold uppercase tracking-wider ${surfaceColor(tournament.surface)}`}
              >
                {tournament.surface}
              </Text>
            )}
            {tournament.city && (
              <Text className="text-xs text-text-secondary">· {tournament.city}</Text>
            )}
            {isFutureEdition && (
              <Text className="text-xs text-text-muted">· {tournament.year}</Text>
            )}
          </View>
        </View>
      </View>

      <FollowButton kind="tournament" slug={tournament.slug} tour={tournament.tour} />

      {tournament.description && (
        <View className="rounded-lg border border-ink-700 bg-ink-900 p-4">
          <Text className="text-sm leading-5 text-text-secondary">{tournament.description}</Text>
          {tournament.wikipedia_url && (
            <Pressable onPress={() => Linking.openURL(tournament.wikipedia_url!)} className="mt-2">
              <Text className="text-xs font-medium text-accent">Read more on Wikipedia →</Text>
            </Pressable>
          )}
        </View>
      )}

      {isFutureEdition && tournament.start_date && (
        <Countdown targetDate={tournament.start_date} />
      )}

      {overview?.stats && <TournamentStatsGrid stats={overview.stats} />}

      <AdSlot slot="tournament-mid" />

      {(live.length > 0 || upcoming.length > 0) && (
        <MatchFilterBar visible={visibleCats} scope={filterScope} />
      )}

      {liveFiltered.length > 0 && (
        <View className="gap-2">
          <SectionHeader title="Today" />
          <TournamentGroups matches={liveFiltered} />
        </View>
      )}
      {upcomingFiltered.length > 0 && (
        <View className="gap-2">
          <SectionHeader title="Upcoming" />
          <TournamentGroups matches={upcomingFiltered.slice(0, 30)} />
        </View>
      )}
      {showBracket && !isPastEdition && (
        <View className="gap-2">
          <SectionHeader title={`Bracket · ${tournament.year}`} />
          <Bracket
            matches={mainDrawMatches}
            drawSize={tournament.draw_size}
            padPlaceholders={true}
          />
        </View>
      )}

      {showLastEdition && overview?.last_edition && (
        <View className="gap-2">
          <SectionHeader
            title="Last edition"
            subtitle={`How the ${overview.last_edition.year} edition ended`}
          />
          <LastEditionCard edition={overview.last_edition} />
        </View>
      )}

      {champions.length > 0 && validTour && (
        <View className="gap-2">
          <SectionHeader title="Past champions" subtitle="Most recent first" />
          <ChampionsList tour={tour as "atp" | "wta"} slug={slug} initial={champions} />
        </View>
      )}

      {overview && overview.records.length > 0 && (
        <View className="gap-2">
          <SectionHeader title="Records" />
          <RecordsList records={overview.records} />
        </View>
      )}

      {(news.length > 0 || videos.length > 0) && (
        <View className="gap-2">
          <SectionHeader title="News & highlights" />
          <FeedList items={mergeFeed(news, videos)} />
        </View>
      )}

      {matches.length === 0 && (
        <View className="rounded-lg border border-dashed border-ink-700 px-4 py-6">
          {isFutureEdition ? (
            <>
              <Text className="text-center text-sm font-medium text-text-secondary">
                The {tournament.year} edition hasn't started yet.
              </Text>
              <Text className="mt-1 text-center text-xs text-text-muted">
                The schedule will populate closer to the start date.
              </Text>
            </>
          ) : (
            <>
              <Text className="text-center text-sm font-medium text-text-secondary">
                We don't have detailed results for the {tournament.year} edition.
              </Text>
              <Text className="mt-1 text-center text-xs text-text-muted">
                {overview?.last_edition
                  ? "See the last edition above for the most recent results we do have."
                  : "Coverage of past editions of this event is limited."}
              </Text>
            </>
          )}
        </View>
      )}
    </Screen>
  );
}
