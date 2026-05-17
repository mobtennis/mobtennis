import { Linking, Pressable, Text, View } from "react-native";
import Svg, { Circle, Path, Rect } from "react-native-svg";

type Props = {
  instagramHandle: string | null;
  twitterHandle: string | null;
  /** Latest post permalink — Phase 2 (paid API or scraper). When present
   *  we'll render an embed via react-native-webview; for now the field is
   *  always null so the embed branch never runs. */
  latestPostUrl: string | null;
  playerName: string;
};

export function SocialCard({
  instagramHandle,
  twitterHandle,
  latestPostUrl,
  playerName,
}: Props) {
  if (!instagramHandle && !twitterHandle) return null;

  return (
    <View className="gap-2">
      <Text className="px-1 text-base font-semibold text-text-primary">Social</Text>

      {instagramHandle && (
        <Pressable
          onPress={() => Linking.openURL(`https://www.instagram.com/${instagramHandle}/`)}
          className="flex-row items-center gap-3 rounded-md border border-ink-700 bg-ink-900 px-3 py-2.5"
        >
          <View className="h-9 w-9 items-center justify-center overflow-hidden rounded-md bg-rose-500">
            <InstagramGlyph />
          </View>
          <View className="min-w-0 flex-1">
            <Text className="text-sm font-semibold text-text-primary">Instagram</Text>
            <Text className="text-[11px] text-text-muted" numberOfLines={1}>
              @{instagramHandle}
            </Text>
          </View>
        </Pressable>
      )}

      {twitterHandle && (
        <Pressable
          onPress={() => Linking.openURL(`https://x.com/${twitterHandle}`)}
          className="flex-row items-center gap-3 rounded-md border border-ink-700 bg-ink-900 px-3 py-2.5"
        >
          <View className="h-9 w-9 items-center justify-center rounded-md bg-text-primary">
            <XGlyph />
          </View>
          <View className="min-w-0 flex-1">
            <Text className="text-sm font-semibold text-text-primary">X</Text>
            <Text className="text-[11px] text-text-muted" numberOfLines={1}>
              @{twitterHandle}
            </Text>
          </View>
        </Pressable>
      )}

      {/* Phase 2: render latest post via react-native-webview when latestPostUrl is set.
          Currently always null — Instagram does not allow profile-level embeds, so the
          post permalink has to come from a paid API or scraper. */}
      {latestPostUrl ? null : null}
    </View>
  );
}

function InstagramGlyph() {
  return (
    <Svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth={2}>
      <Rect x={3} y={3} width={18} height={18} rx={5} />
      <Circle cx={12} cy={12} r={4} />
      <Circle cx={17.5} cy={6.5} r={0.5} fill="white" stroke="none" />
    </Svg>
  );
}

function XGlyph() {
  return (
    <Svg width={16} height={16} viewBox="0 0 24 24" fill="white">
      <Path d="M18.244 2H21.5l-7.46 8.527L22.5 22h-6.815l-5.34-6.99L4.235 22H1l7.96-9.098L1.5 2h6.953l4.836 6.392L18.244 2zm-1.193 18h1.853L7.04 4h-1.97l11.98 16z" />
    </Svg>
  );
}
