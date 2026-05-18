import { useQuery } from "@tanstack/react-query";
import { Link, Stack, useLocalSearchParams } from "expo-router";
import { Image, Linking, Pressable, Text, View } from "react-native";

import { AdSlot } from "@/components/AdSlot";
import { FeedList } from "@/components/FeedList";
import { FollowButton } from "@/components/FollowButton";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { Screen } from "@/components/Screen";
import { SectionHeader } from "@/components/SectionHeader";
import { SocialCard } from "@/components/SocialCard";
import { TournamentGroups } from "@/components/TournamentGroup";
import { TournamentHistoryList } from "@/components/TournamentHistoryList";
import {
  api,
  mergeFeed,
  type MatchSummary,
  type NewsItemSummary,
  type PlayerDetail,
  type TournamentHistoryEntry,
  type VideoItemSummary,
} from "@/lib/api";
import { flagEmoji } from "@/lib/format";

export default function PlayerScreen() {
  const { slug } = useLocalSearchParams<{ slug: string }>();
  const { data: player, refetch, isRefetching } = useQuery({
    queryKey: ["player", slug],
    enabled: !!slug,
    queryFn: () => api<PlayerDetail>(`/api/players/${slug}`),
  });
  const { data: matches = [] } = useQuery({
    queryKey: ["player-matches", slug],
    enabled: !!slug,
    queryFn: () => api<MatchSummary[]>(`/api/players/${slug}/matches?limit=20`),
    refetchInterval: 90_000, // SSE-driven; safety net only
  });
  const { data: news = [] } = useQuery({
    queryKey: ["player-news", slug],
    enabled: !!slug,
    queryFn: () => api<NewsItemSummary[]>(`/api/news?player_slug=${slug}&limit=10`),
  });
  const { data: videos = [] } = useQuery({
    queryKey: ["player-videos", slug],
    enabled: !!slug,
    queryFn: () => api<VideoItemSummary[]>(`/api/videos?player_slug=${slug}&limit=10`),
  });
  const { data: history = [] } = useQuery({
    queryKey: ["player-history", slug],
    enabled: !!slug,
    queryFn: () =>
      api<TournamentHistoryEntry[]>(`/api/players/${slug}/tournament-history?limit=5`),
  });

  if (!player) {
    return (
      <Screen>
        <Text className="text-center text-text-muted">Loading…</Text>
      </Screen>
    );
  }

  const live = matches.filter((m) => m.status === "live" || m.status === "suspended");
  const upcoming = matches.filter((m) => m.status === "scheduled");
  const recent = matches.filter((m) => m.status === "finished").slice(0, 10);

  return (
    <Screen onRefresh={refetch} refreshing={isRefetching}>
      <Stack.Screen options={{ title: player.full_name }} />

      <PlayerHero player={player} />

      <View className="flex-row items-center justify-between gap-3">
        <FollowButton kind="player" slug={player.slug} />
        <Link href={`/h2h/pick?anchor=${player.slug}&tour=${player.tour}` as any} asChild>
          <Pressable className="rounded-full border border-ink-700 bg-ink-900 px-3 py-1.5">
            <Text className="text-xs font-semibold text-text-secondary">Compare H2H →</Text>
          </Pressable>
        </Link>
      </View>

      {player.bio && (
        <View className="rounded-lg border border-ink-700 bg-ink-900 p-4">
          <Text className="text-sm leading-5 text-text-secondary">{player.bio}</Text>
          {player.wikipedia_url && (
            <Pressable onPress={() => Linking.openURL(player.wikipedia_url!)} className="mt-2">
              <Text className="text-xs font-medium text-accent">Read more on Wikipedia →</Text>
            </Pressable>
          )}
        </View>
      )}

      <View className="flex-row flex-wrap gap-2">
        {player.birth_date && <Stat label="Born" value={new Date(player.birth_date).toLocaleDateString()} />}
        {player.height_cm && <Stat label="Height" value={`${player.height_cm} cm`} />}
        {player.plays && <Stat label="Plays" value={player.plays} />}
        {player.turned_pro && <Stat label="Pro since" value={String(player.turned_pro)} />}
      </View>

      <AdSlot slot="player-mid" />

      {live.length > 0 && (
        <View className="gap-2">
          <SectionHeader title="Live" />
          <TournamentGroups matches={live} />
        </View>
      )}
      {upcoming.length > 0 && (
        <View className="gap-2">
          <SectionHeader title="Upcoming" />
          <TournamentGroups matches={upcoming} />
        </View>
      )}
      {recent.length > 0 && (
        <View className="gap-2">
          <SectionHeader title="Recent results" />
          <TournamentGroups matches={recent} />
        </View>
      )}

      {history.length > 0 && (
        <View className="gap-2">
          <SectionHeader title="Tournament history" subtitle="How far they got" />
          <TournamentHistoryList playerSlug={slug ?? ""} initial={history} />
        </View>
      )}

      {(news.length > 0 || videos.length > 0) && (
        <View className="gap-2">
          <SectionHeader title="News & highlights" />
          <FeedList items={mergeFeed(news, videos)} />
        </View>
      )}

      <SocialCard
        instagramHandle={player.instagram_handle}
        twitterHandle={player.twitter_handle}
        latestPostUrl={player.instagram_latest_post_url}
        playerName={player.full_name}
      />

      <ExternalLinks name={player.full_name} tour={player.tour} />
    </Screen>
  );
}

function PlayerHero({ player }: { player: PlayerDetail }) {
  if (player.image_url) {
    return (
      <View className="overflow-hidden rounded-lg border border-ink-700 bg-ink-900">
        <Image source={{ uri: player.image_url }} style={{ width: "100%", height: 180 }} />
        <View className="-mt-12 flex-row items-end gap-3 p-4">
          <Image
            source={{ uri: player.image_url }}
            style={{ width: 76, height: 76, borderRadius: 38, borderWidth: 3, borderColor: "#FFFFFF" }}
          />
          <View className="min-w-0 flex-1 pb-1">
            <Text className="text-xl font-bold text-text-primary" numberOfLines={1}>
              {player.full_name} {flagEmoji(player.country_code)}
            </Text>
            <RankLine player={player} />
          </View>
        </View>
      </View>
    );
  }
  return (
    <View className="flex-row items-center gap-3 rounded-lg border border-ink-700 bg-ink-900 p-4">
      <PlayerAvatar name={player.full_name} imageUrl={null} countryCode={player.country_code} size="lg" />
      <View className="min-w-0 flex-1">
        <Text className="text-xl font-bold text-text-primary">{player.full_name}</Text>
        <RankLine player={player} />
      </View>
    </View>
  );
}

function RankLine({ player }: { player: PlayerDetail }) {
  return (
    <View className="mt-1 flex-row items-center gap-3">
      <View className="rounded-full bg-ink-800 px-2 py-0.5">
        <Text className="text-[10px] font-bold uppercase tracking-wider text-text-primary">
          {player.tour.toUpperCase()}
        </Text>
      </View>
      {player.current_rank != null && (
        <Text className="text-xs text-text-secondary">
          Rank <Text className="font-semibold text-text-primary">#{player.current_rank}</Text>
        </Text>
      )}
      {player.career_high_rank != null && (
        <Text className="text-xs text-text-secondary">
          High <Text className="font-semibold text-text-primary">#{player.career_high_rank}</Text>
        </Text>
      )}
    </View>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <View className="rounded-md border border-ink-700 bg-ink-900 px-3 py-2" style={{ minWidth: 100 }}>
      <Text className="text-[10px] font-bold uppercase tracking-wider text-text-muted">{label}</Text>
      <Text className="mt-0.5 text-sm font-medium text-text-primary">{value}</Text>
    </View>
  );
}

function ExternalLinks({ name, tour }: { name: string; tour: "atp" | "wta" }) {
  const q = encodeURIComponent(name);
  const wikiUrl = `https://en.wikipedia.org/wiki/Special:Search?go=Go&search=${encodeURIComponent(`${name} tennis`)}`;
  const tourUrl = tour === "atp" ? `https://www.atptour.com/en/players?search=${q}` : `https://www.wtatennis.com/search?q=${q}`;
  const ytUrl = `https://www.youtube.com/results?search_query=${encodeURIComponent(`${name} highlights`)}`;
  return (
    <View className="gap-2">
      <SectionHeader title="Find out more" />
      <View className="flex-row flex-wrap gap-2">
        <ExtBtn label={tour === "atp" ? "ATP Tour" : "WTA"} sub="Official" onPress={() => Linking.openURL(tourUrl)} />
        <ExtBtn label="Wikipedia" sub="Career & bio" onPress={() => Linking.openURL(wikiUrl)} />
        <ExtBtn label="YouTube" sub="Highlights" onPress={() => Linking.openURL(ytUrl)} />
      </View>
    </View>
  );
}

function ExtBtn({ label, sub, onPress }: { label: string; sub: string; onPress: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      className="rounded-md border border-ink-700 bg-ink-900 px-3 py-2.5"
      style={{ minWidth: 130 }}
    >
      <Text className="text-sm font-semibold text-text-primary">{label}</Text>
      <Text className="text-[11px] text-text-muted">{sub}</Text>
    </Pressable>
  );
}
