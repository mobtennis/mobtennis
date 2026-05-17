import { useQuery } from "@tanstack/react-query";
import { Text, View } from "react-native";

import { AdSlot } from "@/components/AdSlot";
import { FeedList } from "@/components/FeedList";
import { Screen } from "@/components/Screen";
import {
  api,
  mergeFeed,
  type NewsItemSummary,
  type VideoItemSummary,
} from "@/lib/api";

export default function NewsScreen() {
  const news = useQuery({
    queryKey: ["news"],
    queryFn: () => api<NewsItemSummary[]>("/api/news?limit=50"),
    staleTime: 2 * 60_000,
  });
  const videos = useQuery({
    queryKey: ["videos"],
    queryFn: () => api<VideoItemSummary[]>("/api/videos?limit=20"),
    staleTime: 2 * 60_000,
  });

  const items = mergeFeed(news.data ?? [], videos.data ?? []);
  const above = items.slice(0, 5);
  const below = items.slice(5);
  const refetching = news.isRefetching || videos.isRefetching;

  return (
    <Screen
      onRefresh={async () => {
        await Promise.all([news.refetch(), videos.refetch()]);
      }}
      refreshing={refetching}
    >
      <View className="px-1">
        <Text className="text-2xl font-bold text-text-primary">News</Text>
        <Text className="mt-1 text-sm text-text-secondary">
          Headlines and highlights from across the tennis world.
        </Text>
      </View>
      <FeedList items={above} />
      {below.length > 0 && <AdSlot slot="news-mid" />}
      {below.length > 0 && <FeedList items={below} />}
    </Screen>
  );
}
