import { useQuery } from "@tanstack/react-query";
import { Link, Stack, useLocalSearchParams } from "expo-router";
import { Pressable, Text, View } from "react-native";

import { PlayerAvatar } from "@/components/PlayerAvatar";
import { Screen } from "@/components/Screen";
import { SectionHeader } from "@/components/SectionHeader";
import { TournamentGroups } from "@/components/TournamentGroup";
import { api, type MatchSummary, type PlayerSummary } from "@/lib/api";
import { surfaceColor } from "@/lib/format";

type H2H = {
  player1: PlayerSummary;
  player2: PlayerSummary;
  p1_wins: number;
  p2_wins: number;
  matches: MatchSummary[];
  surface_splits: { surface: string; p1_wins: number; p2_wins: number }[];
};

export default function H2HScreen() {
  const { matchup } = useLocalSearchParams<{ matchup: string }>();
  const { data, refetch, isRefetching } = useQuery({
    queryKey: ["h2h", matchup],
    enabled: !!matchup && matchup.includes("-vs-"),
    queryFn: () => api<H2H>(`/api/h2h/${matchup}`),
  });

  if (!data) {
    return (
      <Screen>
        <Text className="text-center text-text-muted">Loading…</Text>
      </Screen>
    );
  }

  const total = data.p1_wins + data.p2_wins;
  const p1Pct = total ? (data.p1_wins / total) * 100 : 50;

  return (
    <Screen onRefresh={refetch} refreshing={isRefetching}>
      <Stack.Screen options={{ title: "Head-to-head" }} />

      <View className="rounded-lg border border-ink-700 bg-ink-900 p-4">
        <Text className="text-center text-xs uppercase tracking-wider text-text-muted">
          Head-to-head
        </Text>
        <View className="mt-3 flex-row items-center justify-between">
          <Link href={`/players/${data.player1.slug}` as any} asChild>
            <Pressable className="flex-1 items-center gap-2">
              <PlayerAvatar
                name={data.player1.full_name}
                imageUrl={data.player1.image_url}
                countryCode={data.player1.country_code}
                size="md"
              />
              <Text className="text-sm font-semibold text-text-primary" numberOfLines={1}>
                {data.player1.full_name}
              </Text>
            </Pressable>
          </Link>
          <View className="flex-1 items-center">
            <Text className="text-3xl font-bold text-text-primary">
              {data.p1_wins} <Text className="text-text-muted">–</Text> {data.p2_wins}
            </Text>
            <Text className="mt-1 text-[10px] uppercase tracking-wider text-text-muted">
              {total} {total === 1 ? "match" : "matches"}
            </Text>
          </View>
          <Link href={`/players/${data.player2.slug}` as any} asChild>
            <Pressable className="flex-1 items-center gap-2">
              <PlayerAvatar
                name={data.player2.full_name}
                imageUrl={data.player2.image_url}
                countryCode={data.player2.country_code}
                size="md"
              />
              <Text className="text-sm font-semibold text-text-primary" numberOfLines={1}>
                {data.player2.full_name}
              </Text>
            </Pressable>
          </Link>
        </View>

        <View className="mt-4 h-1.5 w-full overflow-hidden rounded-full bg-ink-700">
          <View className="h-full bg-accent" style={{ width: `${p1Pct}%` }} />
        </View>
      </View>

      {data.surface_splits.length > 0 && (
        <View className="gap-2">
          <SectionHeader title="By surface" />
          <View className="gap-2">
            {data.surface_splits.map((s) => {
              const t = s.p1_wins + s.p2_wins;
              const pct = t ? (s.p1_wins / t) * 100 : 50;
              return (
                <View key={s.surface} className="rounded-md border border-ink-700 bg-ink-900 p-3">
                  <View className="flex-row items-center justify-between">
                    <Text
                      className={`text-xs font-bold uppercase tracking-wider ${surfaceColor(s.surface)}`}
                    >
                      {s.surface}
                    </Text>
                    <Text className="text-xs text-text-secondary">
                      {s.p1_wins} – {s.p2_wins}
                    </Text>
                  </View>
                  <View className="mt-2 h-1 w-full overflow-hidden rounded-full bg-ink-700">
                    <View className="h-full bg-accent" style={{ width: `${pct}%` }} />
                  </View>
                </View>
              );
            })}
          </View>
        </View>
      )}

      {data.matches.length > 0 && (
        <View className="gap-2">
          <SectionHeader title="Past meetings" />
          <TournamentGroups matches={data.matches} />
        </View>
      )}
    </Screen>
  );
}
