import { Link } from "expo-router";
import { Pressable, Text, View } from "react-native";

import { MatchCard } from "@/components/MatchCard";
import type { IndexTournament, MatchSummary } from "@/lib/api";

/**
 * Tournament block used on the Live tab for big-tier events — shows
 * live matches and (for big tournaments) up to 2 upcoming with a
 * "See all" link to the tournament detail page.
 */
export function LiveTournamentBlock({
  tournament,
  liveMatches,
  upcomingMatches,
}: {
  tournament: IndexTournament;
  liveMatches: MatchSummary[];
  upcomingMatches: MatchSummary[];
}) {
  const href =
    `/tournaments/${tournament.tour}/${tournament.slug}` as const;

  return (
    <View className="overflow-hidden rounded-lg border border-ink-700 bg-ink-900">
      <Link href={href as any} asChild>
        <Pressable className="flex-row items-center justify-between border-b border-ink-700 bg-ink-800 px-3 py-2">
          <Text className="flex-1 text-sm font-semibold text-text-primary" numberOfLines={1}>
            {tournament.name}
          </Text>
          <Text className="ml-2 text-[11px] font-semibold text-text-muted">
            {liveMatches.length > 0 ? `${liveMatches.length} live` : "Upcoming"}
          </Text>
        </Pressable>
      </Link>
      <View className="gap-px">
        {liveMatches.map((m) => (
          <View key={m.id}>
            <MatchCard match={m} />
          </View>
        ))}
        {upcomingMatches.length > 0 && (
          <>
            <View className="bg-ink-900 px-3 py-1">
              <Text className="text-[10px] font-bold uppercase tracking-wider text-text-muted">
                Next up
              </Text>
            </View>
            {upcomingMatches.map((m) => (
              <View key={m.id}>
                <MatchCard match={m} />
              </View>
            ))}
          </>
        )}
      </View>
      <Link href={href as any} asChild>
        <Pressable className="border-t border-ink-700 bg-ink-800 px-3 py-2">
          <Text className="text-center text-[11px] font-semibold text-accent">
            See all matches →
          </Text>
        </Pressable>
      </Link>
    </View>
  );
}
