import { Image, Linking, Pressable, Text, View } from "react-native";
import Svg, { Path } from "react-native-svg";

import { analytics } from "@/lib/analytics";
import { EVENTS } from "@/lib/analytics";
import type { VideoItemSummary } from "@/lib/api";
import { parseUtcIso } from "@/lib/format";

/**
 * YouTube highlight card for mobile. Tapping opens the video in the
 * YouTube app (if installed) or the device browser.
 *
 * We don't embed an inline iframe player — that would require a
 * native WebView dependency (`react-native-webview` /
 * `react-native-youtube-iframe`) which breaks Expo Go. The
 * tap-to-open pattern keeps the app installable from Expo Go for
 * testing and matches the UX of most native sports apps.
 */
export function VideoCard({ video }: { video: VideoItemSummary }) {
  const onOpen = () => {
    analytics.track(EVENTS.newsClicked, {
      kind: "video",
      video_id: video.video_id,
      source: video.source,
    });
    void Linking.openURL(`https://www.youtube.com/watch?v=${video.video_id}`);
  };

  const channelLabel = video.channel_name ?? video.source;
  const published = parseUtcIso(video.published_at).toLocaleDateString([], {
    month: "short",
    day: "numeric",
  });

  return (
    <Pressable
      onPress={onOpen}
      className="overflow-hidden rounded-lg border border-ink-700 bg-ink-900"
    >
      <View className="relative aspect-video w-full bg-ink-950">
        {video.thumbnail_url && (
          <Image
            source={{ uri: video.thumbnail_url }}
            style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
            resizeMode="cover"
          />
        )}
        <View className="absolute inset-0 items-center justify-center">
          <View className="h-14 w-14 items-center justify-center rounded-full bg-black/60">
            <Svg width="22" height="22" viewBox="0 0 24 24">
              <Path d="M8 5v14l11-7z" fill="#FFFFFF" />
            </Svg>
          </View>
        </View>
      </View>
      <View className="px-3 py-2">
        <Text className="text-sm font-semibold text-text-primary" numberOfLines={2}>
          {video.title}
        </Text>
        <Text className="mt-1 text-[11px] text-text-muted">
          {channelLabel} · {published}
        </Text>
      </View>
    </Pressable>
  );
}
