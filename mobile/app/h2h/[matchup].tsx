import { useQuery } from "@tanstack/react-query";
import { Link, Stack, useLocalSearchParams } from "expo-router";
import { Pressable, Text, View } from "react-native";

import { ChangeOpponentLink } from "@/components/ChangeOpponentLink";
import { OpponentPicker } from "@/components/OpponentPicker";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { Screen } from "@/components/Screen";
import { SectionHeader } from "@/components/SectionHeader";
import { TournamentGroups } from "@/components/TournamentGroup";
import { api, type MatchSummary, type PlayerDetail, type PlayerSummary } from "@/lib/api";
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
  const [s1, s2] = (matchup ?? "").split("-vs-", 2);
  const halfFormed = !!(matchup && matchup.includes("-vs-") && (!s1 || !s2));

  // Full-data fetch only when both slugs are present.
  const fullQuery = useQuery({
    queryKey: ["h2h", matchup],
    enabled: !!matchup && matchup.includes("-vs-") && !halfFormed,
    queryFn: () => api<H2H>(`/api/h2h/${matchup}`),
  });

  // For the half-formed URL case, pull the known player so we can
  // render their avatar + restrict the picker to their tour.
  const anchorSlug = halfFormed ? (s1 || s2) : null;
  const anchorQuery = useQuery({
    queryKey: ["player", anchorSlug],
    enabled: !!anchorSlug,
    queryFn: () => api<PlayerDetail>(`/api/players/${anchorSlug}`),
  });

  if (halfFormed) {
    const anchor = anchorQuery.data;
    if (!anchor) {
      return (
        <Screen>
          <Stack.Screen options={{ title: "Head-to-head" }} />
          <Text className="text-center text-text-muted">Loading…</Text>
        </Screen>
      );
    }
    return (
      <Screen>
        <Stack.Screen options={{ title: "Head-to-head" }} />
        <PartialH2HCard anchor={anchor} anchorOnLeft={!!s1} />
      </Screen>
    );
  }

  const data = fullQuery.data;
  if (!data) {
    return (
      <Screen>
        <Stack.Screen options={{ title: "Head-to-head" }} />
        <Text className="text-center text-text-muted">Loading…</Text>
      </Screen>
    );
  }

  const total = data.p1_wins + data.p2_wins;
  const p1Pct = total ? (data.p1_wins / total) * 100 : 50;

  return (
    <Screen onRefresh={fullQuery.refetch} refreshing={fullQuery.isRefetching}>
      <Stack.Screen options={{ title: "Head-to-head" }} />

      <View className="rounded-lg border border-ink-700 bg-ink-900 p-4">
        <Text className="text-center text-xs uppercase tracking-wider text-text-muted">
          Head-to-head
        </Text>
        <View className="mt-3 flex-row items-start justify-between">
          {/* Each side has a "change opponent" link. Anchor passed to it
              is the OTHER player — picking under player 1 keeps player 2
              fixed and swaps player 1, and vice versa. */}
          <View className="flex-1 items-center gap-2">
            <Link href={`/players/${data.player1.slug}` as any} asChild>
              <Pressable className="items-center gap-2">
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
            <ChangeOpponentLink
              anchorSlug={data.player2.slug}
              tourFilter={data.player2.tour}
            />
          </View>
          <View className="flex-1 items-center">
            <Text className="text-3xl font-bold text-text-primary">
              {data.p1_wins} <Text className="text-text-muted">–</Text> {data.p2_wins}
            </Text>
            <Text className="mt-1 text-[10px] uppercase tracking-wider text-text-muted">
              {total} {total === 1 ? "match" : "matches"}
            </Text>
          </View>
          <View className="flex-1 items-center gap-2">
            <Link href={`/players/${data.player2.slug}` as any} asChild>
              <Pressable className="items-center gap-2">
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
            <ChangeOpponentLink
              anchorSlug={data.player1.slug}
              tourFilter={data.player1.tour}
            />
          </View>
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

/** Half-formed URL layout: known player on one side, picker on the
 * other. Mirrors the web behaviour. */
function PartialH2HCard({
  anchor,
  anchorOnLeft,
}: {
  anchor: PlayerDetail;
  anchorOnLeft: boolean;
}) {
  const anchorBlock = (
    <Link href={`/players/${anchor.slug}` as any} asChild>
      <Pressable className="flex-1 items-center gap-2">
        <PlayerAvatar
          name={anchor.full_name}
          imageUrl={anchor.image_url}
          countryCode={anchor.country_code}
          size="md"
        />
        <Text className="text-sm font-semibold text-text-primary" numberOfLines={1}>
          {anchor.full_name}
        </Text>
      </Pressable>
    </Link>
  );
  const pickerBlock = (
    <View className="flex-1 items-center gap-2">
      <View className="h-14 w-14 items-center justify-center rounded-full border border-dashed border-ink-700">
        <Text className="text-2xl text-text-muted">?</Text>
      </View>
      <OpponentPicker anchorSlug={anchor.slug} tourFilter={anchor.tour} />
    </View>
  );
  return (
    <View className="rounded-lg border border-ink-700 bg-ink-900 p-4">
      <Text className="text-center text-xs uppercase tracking-wider text-text-muted">
        Head-to-head
      </Text>
      <View className="mt-3 flex-row items-start justify-between gap-2">
        {anchorOnLeft ? anchorBlock : pickerBlock}
        <View className="flex-1 items-center">
          <Text className="text-3xl font-bold text-text-muted">vs</Text>
          <Text className="mt-1 text-[10px] uppercase tracking-wider text-text-muted">
            pick an opponent
          </Text>
        </View>
        {anchorOnLeft ? pickerBlock : anchorBlock}
      </View>
    </View>
  );
}
