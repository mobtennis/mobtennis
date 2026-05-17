import { useQuery } from "@tanstack/react-query";
import { Text, View } from "react-native";

import { AdSlot } from "@/components/AdSlot";
import { LiveDot } from "@/components/LiveDot";
import { LiveTournamentBlock } from "@/components/LiveTournamentBlock";
import { MatchCard } from "@/components/MatchCard";
import { MatchFilterBar } from "@/components/MatchFilters";
import { Screen } from "@/components/Screen";
import { SectionHeader } from "@/components/SectionHeader";
import { TournamentCard } from "@/components/TournamentCard";
import {
  api,
  type IndexTournament,
  type MatchSummary,
  type TournamentsIndexResponse,
} from "@/lib/api";
import { isLocalToday } from "@/lib/format";
import { useFollows } from "@/lib/follows";
import { passesFilter, useMatchFilters } from "@/lib/match-filters";
import { tierWeight } from "@/lib/tier";

const TOP_MATCHES = 5;
const UPCOMING_PER_BIG = 2;
const BIG_TIERS = new Set([
  "grand_slam",
  "atp_1000",
  "wta_1000",
  "atp_finals",
  "wta_finals",
]);

export default function LiveScreen() {
  const { playerSlugs, tournamentKeys } = useFollows();
  // Live tab is multi-tour — all 5 chips visible. Hook still returns
  // `effective` so the fallback-to-all rule applies if someone has
  // emptied their selection.
  const { effective } = useMatchFilters();

  const { data: matches = [], refetch: r1, isRefetching: ir1 } = useQuery({
    queryKey: ["matches-live"],
    queryFn: () => api<MatchSummary[]>("/api/matches/live"),
    // SSE drives realtime updates via LiveStreamSubscriber; this is the
    // safety net if the stream drops.
    refetchInterval: 60_000,
  });
  const { data: upcomingFeatured = [], refetch: r3, isRefetching: ir3 } = useQuery({
    queryKey: ["matches-upcoming-featured"],
    queryFn: () => api<MatchSummary[]>("/api/matches/upcoming-featured"),
    // Upcoming changes slowly relative to live scores — 2 min is plenty.
    refetchInterval: 120_000,
  });
  const { data: tIndex, refetch: r2, isRefetching: ir2 } = useQuery({
    queryKey: ["tournaments-index"],
    queryFn: () => api<TournamentsIndexResponse>("/api/tournaments/index"),
    staleTime: 30_000,
  });

  const matchHasFollowed = (m: MatchSummary): boolean =>
    (m.player1?.slug != null && playerSlugs.has(m.player1.slug)) ||
    (m.player2?.slug != null && playerSlugs.has(m.player2.slug));

  const filteredMatches = matches.filter((m) => passesFilter(m, effective));
  const sorted = [...filteredMatches].sort((a, b) => {
    const af = matchHasFollowed(a) ? 0 : 1;
    const bf = matchHasFollowed(b) ? 0 : 1;
    if (af !== bf) return af - bf;
    const dt = tierWeight(a.tournament_category) - tierWeight(b.tournament_category);
    if (dt !== 0) return dt;
    return a.tournament_name.localeCompare(b.tournament_name);
  });
  const top = sorted.slice(0, TOP_MATCHES);

  const rawLiveTournaments = tIndex?.sections.find((s) => s.key === "live")?.tournaments ?? [];
  const liveTournaments = [...rawLiveTournaments].sort((a, b) => {
    const af = tournamentKeys.has(`${a.tour}/${a.slug}`) ? 0 : 1;
    const bf = tournamentKeys.has(`${b.tour}/${b.slug}`) ? 0 : 1;
    if (af !== bf) return af - bf;
    return tierWeight(a.category) - tierWeight(b.category);
  });

  const followedMatchCount = sorted.filter(matchHasFollowed).length;

  // Big tournaments get the always-visible block treatment: live matches
  // inline + up to 2 upcoming + "See all" link. Small tournaments keep
  // /api/matches/live returns LIVE + SUSPENDED + FINISHED-in-last-36h.
  // The server can't know the client's timezone, so we narrow the
  // FINISHED set to "today in local time" here — keeps recently-
  // completed matches in view through end-of-day without users having
  // to dig into the bracket.
  const todaysMatches = matches.filter(
    (m) =>
      m.status === "live" ||
      m.status === "suspended" ||
      (m.status === "finished" && isLocalToday(m.scheduled_at)),
  );

  // the compact card. Group both pools by tournament key first, then
  // walk the in-progress list to assemble blocks vs cards.
  const liveByKey = new Map<string, MatchSummary[]>();
  for (const m of todaysMatches) {
    const k = `${m.tournament_tour ?? ""}/${m.tournament_slug}/${m.tournament_year}`;
    if (!liveByKey.has(k)) liveByKey.set(k, []);
    liveByKey.get(k)!.push(m);
  }
  const upcomingByKey = new Map<string, MatchSummary[]>();
  for (const m of upcomingFeatured) {
    const k = `${m.tournament_tour ?? ""}/${m.tournament_slug}/${m.tournament_year}`;
    if (!upcomingByKey.has(k)) upcomingByKey.set(k, []);
    upcomingByKey.get(k)!.push(m);
  }
  const collectByKeys = (
    t: IndexTournament,
    bag: Map<string, MatchSummary[]>,
  ): MatchSummary[] => {
    const tours = t.tours.length > 0 ? t.tours : [t.tour];
    return tours.flatMap((tour) => bag.get(`${tour}/${t.slug}/${t.year}`) ?? []);
  };

  const bigTournaments: {
    t: IndexTournament;
    live: MatchSummary[];
    upcoming: MatchSummary[];
  }[] = [];
  const smallCards: IndexTournament[] = [];
  for (const t of liveTournaments) {
    const isBig = BIG_TIERS.has(t.category);
    const live = collectByKeys(t, liveByKey).filter((m) => passesFilter(m, effective));
    if (!isBig) {
      // Small tournament: only render if it has live matches surviving the filter.
      const anyLive = collectByKeys(t, liveByKey);
      if (anyLive.length > 0 && live.length === 0) continue; // filtered to nothing
      if (anyLive.length === 0) continue;
      smallCards.push(t);
      continue;
    }
    const upcoming = collectByKeys(t, upcomingByKey)
      .filter((m) => passesFilter(m, effective))
      .slice(0, UPCOMING_PER_BIG);
    bigTournaments.push({ t, live, upcoming });
  }

  const onRefresh = async () => {
    await Promise.all([r1(), r2(), r3()]);
  };

  if (matches.length === 0 && liveTournaments.length === 0) {
    return (
      <Screen onRefresh={onRefresh} refreshing={ir1 || ir2 || ir3}>
        <View className="rounded-lg border border-dashed border-ink-700 bg-ink-900 px-4 py-16">
          <Text className="text-center text-sm text-text-secondary">No matches in play right now.</Text>
        </View>
      </Screen>
    );
  }

  return (
    <Screen onRefresh={onRefresh} refreshing={ir1 || ir2 || ir3}>
      <View className="px-1">
        <View className="flex-row items-center gap-2">
          <LiveDot label={false} />
          <Text className="text-sm text-text-secondary">
            {filteredMatches.length} {filteredMatches.length === 1 ? "match" : "matches"} ·{" "}
            {liveTournaments.length} {liveTournaments.length === 1 ? "tournament" : "tournaments"}
          </Text>
        </View>
      </View>

      <MatchFilterBar />

      {top.length > 0 && (
        <View className="gap-2">
          <SectionHeader
            title="Top matches"
            subtitle={
              followedMatchCount > 0
                ? `${followedMatchCount} from who you follow · then by importance`
                : "Sorted by tournament importance"
            }
          />
          <View className="gap-2">
            {top.map((m) => (
              <MatchCard key={m.id} match={m} />
            ))}
          </View>
        </View>
      )}

      <AdSlot slot="home-mid" />

      {bigTournaments.length > 0 && (
        <View className="gap-2">
          <SectionHeader
            title="Featured tournaments"
            subtitle="Live + next up"
          />
          <View className="gap-3">
            {bigTournaments.map(({ t, live, upcoming }) => (
              <LiveTournamentBlock
                key={`${t.tour}/${t.slug}/${t.year}`}
                tournament={t}
                liveMatches={live}
                upcomingMatches={upcoming}
              />
            ))}
          </View>
        </View>
      )}

      {smallCards.length > 0 && (
        <View className="gap-2">
          <SectionHeader
            title="Other tournaments live"
            subtitle="Tap to see all matches"
          />
          <View className="gap-2">
            {smallCards.map((t) => (
              <TournamentCard key={`${t.slug}-${t.year}-${t.tour}`} t={t} />
            ))}
          </View>
        </View>
      )}
    </Screen>
  );
}
