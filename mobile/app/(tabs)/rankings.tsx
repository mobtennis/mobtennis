import { useQuery } from "@tanstack/react-query";
import { Link } from "expo-router";
import { Pressable, Text, View } from "react-native";

import { AdSlot } from "@/components/AdSlot";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { Screen } from "@/components/Screen";
import { api, type RankingsResponse } from "@/lib/api";
import { flagEmoji } from "@/lib/format";
import { usePreferredTour } from "@/lib/preferred-tour";

export default function RankingsScreen() {
  // Use the shared preferred-tour store as the source of truth: switching
  // tabs here also updates the global preference, so joint tournaments
  // default to the user's last-picked tour.
  const { tour, setTour } = usePreferredTour();

  const { data, refetch, isRefetching } = useQuery({
    queryKey: ["rankings", tour],
    queryFn: () => api<RankingsResponse>(`/api/rankings/${tour}?limit=200`),
    staleTime: 5 * 60_000,
  });

  return (
    <Screen onRefresh={refetch} refreshing={isRefetching}>
      <View className="px-1">
        <Text className="text-sm text-text-secondary">
          {data ? `Week of ${new Date(data.week).toLocaleDateString()}` : "Loading…"}
        </Text>
      </View>

      <View className="flex-row gap-2">
        {(["atp", "wta"] as const).map((t) => {
          const isActive = tour === t;
          return (
            <Pressable
              key={t}
              onPress={() => setTour(t)}
              className={`rounded-full border px-3 py-1.5 ${
                isActive ? "border-accent bg-accent/10" : "border-ink-700 bg-ink-900"
              }`}
            >
              <Text className={`text-xs font-bold uppercase tracking-wider ${isActive ? "text-accent" : "text-text-secondary"}`}>
                {t}
              </Text>
            </Pressable>
          );
        })}
      </View>

      <View className="overflow-hidden rounded-lg border border-ink-700 bg-ink-900">
        {(data?.rows ?? []).slice(0, 25).map((row, i) => (
          <Link key={`${row.rank}-${row.player.slug}`} href={`/players/${row.player.slug}` as any} asChild>
            <Pressable
              className={`flex-row items-center gap-3 px-3 py-2.5 ${i > 0 ? "border-t border-ink-700" : ""}`}
            >
              <Text className="w-7 text-right text-sm font-bold text-text-secondary">
                {row.rank}
              </Text>
              <PlayerAvatar
                name={row.player.full_name}
                imageUrl={row.player.image_url}
                countryCode={row.player.country_code}
              />
              <Text className="flex-1 text-sm font-medium text-text-primary" numberOfLines={1}>
                {row.player.full_name}
              </Text>
              <Text className="text-xs">{flagEmoji(row.player.country_code)}</Text>
              {row.points && (
                <Text className="w-16 text-right text-xs text-text-secondary">
                  {row.points.toLocaleString()} pts
                </Text>
              )}
            </Pressable>
          </Link>
        ))}
      </View>

      {(data?.rows ?? []).length > 25 && <AdSlot slot="rankings-mid" />}

      {(data?.rows ?? []).length > 25 && (
        <View className="overflow-hidden rounded-lg border border-ink-700 bg-ink-900">
          {(data?.rows ?? []).slice(25).map((row, i) => (
            <Link key={`${row.rank}-${row.player.slug}`} href={`/players/${row.player.slug}` as any} asChild>
              <Pressable
                className={`flex-row items-center gap-3 px-3 py-2.5 ${i > 0 ? "border-t border-ink-700" : ""}`}
              >
                <Text className="w-7 text-right text-sm font-bold text-text-secondary">
                  {row.rank}
                </Text>
                <PlayerAvatar
                  name={row.player.full_name}
                  imageUrl={row.player.image_url}
                  countryCode={row.player.country_code}
                />
                <Text className="flex-1 text-sm font-medium text-text-primary" numberOfLines={1}>
                  {row.player.full_name}
                </Text>
                <Text className="text-xs">{flagEmoji(row.player.country_code)}</Text>
                {row.points && (
                  <Text className="w-16 text-right text-xs text-text-secondary">
                    {row.points.toLocaleString()} pts
                  </Text>
                )}
              </Pressable>
            </Link>
          ))}
        </View>
      )}
    </Screen>
  );
}
