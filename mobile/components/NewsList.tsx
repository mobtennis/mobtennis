import { Image, Linking, Pressable, Text, View } from "react-native";

import type { NewsItemSummary } from "@/lib/api";
import { formatRelative } from "@/lib/format";

export function NewsList({ items, compact = false }: { items: NewsItemSummary[]; compact?: boolean }) {
  if (items.length === 0) {
    return (
      <View className="rounded-lg border border-dashed border-ink-700 px-4 py-8">
        <Text className="text-center text-text-muted">No news yet.</Text>
      </View>
    );
  }
  return (
    <View className="gap-2">
      {items.map((item) => (
        <Pressable
          key={item.id}
          onPress={() => Linking.openURL(item.source_url)}
          className="flex-row gap-3 rounded-md border border-ink-700 bg-ink-900 p-3"
        >
          {item.image_url && !compact && (
            <Image source={{ uri: item.image_url }} style={{ width: 80, height: 80, borderRadius: 6 }} />
          )}
          <View className="min-w-0 flex-1">
            <Text className="text-sm font-semibold text-text-primary" numberOfLines={2}>
              {item.title}
            </Text>
            {item.summary && !compact && (
              <Text className="mt-1 text-xs leading-4 text-text-secondary" numberOfLines={2}>
                {item.summary}
              </Text>
            )}
            <View className="mt-1 flex-row items-center gap-2">
              <Text className="text-[11px] font-medium uppercase tracking-wider text-text-muted">
                {item.source}
              </Text>
              <Text className="text-[11px] text-text-muted">·</Text>
              <Text className="text-[11px] text-text-muted">{formatRelative(item.published_at)}</Text>
            </View>
          </View>
        </Pressable>
      ))}
    </View>
  );
}
