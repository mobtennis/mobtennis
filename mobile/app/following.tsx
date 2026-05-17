import { useQuery } from "@tanstack/react-query";
import { Link, Stack } from "expo-router";
import { Pressable, Text, View } from "react-native";

import { FeedList } from "@/components/FeedList";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { Screen } from "@/components/Screen";
import { SectionHeader } from "@/components/SectionHeader";
import { TournamentGroups } from "@/components/TournamentGroup";
import {
  api,
  mergeFeed,
  type MatchSummary,
  type NewsItemSummary,
  type PlayerSummary,
  type VideoItemSummary,
} from "@/lib/api";
import { useFollows } from "@/lib/follows";

export default function FollowingScreen() {
  const { follows, isLoading } = useFollows();
  const playerSlugs = follows.filter((f) => f.kind === "player").map((f) => f.target_slug);
  const followedTournaments = follows.filter((f) => f.kind === "tournament");

  const { data: players = [] } = useQuery<PlayerSummary[]>({
    queryKey: ["followed-players", playerSlugs.join(",")],
    enabled: playerSlugs.length > 0,
    queryFn: async () => {
      const all = await Promise.all(
        playerSlugs.map((s) => api<PlayerSummary>(`/api/players/${s}`).catch(() => null)),
      );
      return all.filter((p): p is PlayerSummary => p !== null);
    },
  });

  const { data: matches = [], refetch, isRefetching } = useQuery<MatchSummary[]>({
    queryKey: ["followed-matches", playerSlugs.join(",")],
    enabled: playerSlugs.length > 0,
    refetchInterval: 90_000, // SSE-driven; safety net only
    queryFn: async () => {
      const all = await Promise.all(
        playerSlugs.map((s) =>
          api<MatchSummary[]>(`/api/players/${s}/matches?limit=10`).catch(() => []),
        ),
      );
      const merged = all.flat();
      const seen = new Set<number>();
      return merged.filter((m) => (seen.has(m.id) ? false : (seen.add(m.id), true)));
    },
  });

  const { data: news = [] } = useQuery<NewsItemSummary[]>({
    queryKey: ["followed-news", playerSlugs.join(",")],
    enabled: playerSlugs.length > 0,
    queryFn: async () => {
      const all = await Promise.all(
        playerSlugs.map((s) =>
          api<NewsItemSummary[]>(`/api/news?player_slug=${s}&limit=8`).catch(() => []),
        ),
      );
      const merged = all.flat();
      const seen = new Set<number>();
      return merged
        .filter((n) => (seen.has(n.id) ? false : (seen.add(n.id), true)))
        .sort((a, b) => +new Date(b.published_at) - +new Date(a.published_at))
        .slice(0, 12);
    },
  });
  const { data: videos = [] } = useQuery<VideoItemSummary[]>({
    queryKey: ["followed-videos", playerSlugs.join(",")],
    enabled: playerSlugs.length > 0,
    queryFn: async () => {
      const all = await Promise.all(
        playerSlugs.map((s) =>
          api<VideoItemSummary[]>(`/api/videos?player_slug=${s}&limit=8`).catch(() => []),
        ),
      );
      const merged = all.flat();
      const seen = new Set<number>();
      return merged
        .filter((v) => (seen.has(v.id) ? false : (seen.add(v.id), true)))
        .sort((a, b) => +new Date(b.published_at) - +new Date(a.published_at))
        .slice(0, 12);
    },
  });

  if (isLoading) {
    return (
      <Screen>
        <Stack.Screen options={{ title: "Following" }} />
        <Text className="text-center text-text-muted">Loading…</Text>
      </Screen>
    );
  }

  if (follows.length === 0) {
    return (
      <Screen>
        <Stack.Screen options={{ title: "Following" }} />
        <View className="rounded-lg border border-dashed border-ink-700 px-4 py-12">
          <Text className="text-center text-base font-semibold text-text-primary">
            Nothing followed yet.
          </Text>
          <Text className="mt-1 text-center text-sm text-text-muted">
            Tap the star on any player or tournament to add them here.
          </Text>
        </View>
        <Link href={"/credits" as any} asChild>
          <Pressable className="mt-4 self-center py-2">
            <Text className="text-[11px] text-text-muted underline">
              Credits & data sources
            </Text>
          </Pressable>
        </Link>
      </Screen>
    );
  }

  const live = matches.filter((m) => m.status === "live" || m.status === "suspended");
  const upcoming = matches.filter((m) => m.status === "scheduled").slice(0, 10);

  return (
    <Screen onRefresh={refetch} refreshing={isRefetching}>
      <Stack.Screen options={{ title: "Following" }} />
      {players.length > 0 && (
        <View className="gap-2">
          <SectionHeader title="Players you follow" />
          <View className="flex-row flex-wrap gap-3">
            {players.map((p) => (
              <Link key={p.slug} href={`/players/${p.slug}` as any} asChild>
                <Pressable className="w-20 items-center gap-1.5 rounded-lg border border-ink-700 bg-ink-900 p-2">
                  <PlayerAvatar
                    name={p.full_name}
                    imageUrl={p.image_url}
                    countryCode={p.country_code}
                    size="md"
                  />
                  <Text className="text-[11px] font-medium text-text-primary" numberOfLines={1}>
                    {p.full_name}
                  </Text>
                  {p.current_rank != null && (
                    <Text className="text-[10px] text-text-muted">#{p.current_rank}</Text>
                  )}
                </Pressable>
              </Link>
            ))}
          </View>
        </View>
      )}

      {live.length > 0 && (
        <View className="gap-2">
          <SectionHeader title="Live now" />
          <TournamentGroups matches={live} />
        </View>
      )}
      {upcoming.length > 0 && (
        <View className="gap-2">
          <SectionHeader title="Coming up" />
          <TournamentGroups matches={upcoming} />
        </View>
      )}

      {followedTournaments.length > 0 && (
        <View className="gap-2">
          <SectionHeader title="Tournaments you follow" />
          <View className="gap-2">
            {followedTournaments.map((f) => {
              const tour = f.target_tour ?? "atp";
              return (
                <Link
                  key={`${tour}-${f.target_slug}`}
                  href={`/tournaments/${tour}/${f.target_slug}` as any}
                  asChild
                >
                  <Pressable className="flex-row items-center justify-between rounded-md border border-ink-700 bg-ink-900 px-3 py-3">
                    <Text className="text-sm font-medium text-text-primary">
                      {f.target_slug.replace(/-/g, " ")}
                    </Text>
                    <Text className="text-[10px] uppercase tracking-wider text-text-muted">{tour}</Text>
                  </Pressable>
                </Link>
              );
            })}
          </View>
        </View>
      )}

      {(news.length > 0 || videos.length > 0) && (
        <View className="gap-2">
          <SectionHeader title="News & highlights about who you follow" />
          <FeedList items={mergeFeed(news, videos)} compact />
        </View>
      )}

      <Link href={"/credits" as any} asChild>
        <Pressable className="mt-4 self-center py-2">
          <Text className="text-[11px] text-text-muted underline">
            Credits & data sources
          </Text>
        </Pressable>
      </Link>
    </Screen>
  );
}
