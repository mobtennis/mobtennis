import { Text, View } from "react-native";

type Props = {
  slot: string;
};

/**
 * Mobile ad placeholder. Render mode is controlled by EXPO_PUBLIC_ADS_MODE:
 *   "off"         → renders nothing (default in prod builds)
 *   "placeholder" → dashed-border placeholder (default in __DEV__)
 *   "live"        → real ad markup (TBD once AdMob is wired up)
 *
 * Future swap target: react-native-google-mobile-ads
 *   <BannerAd unitId={...} size={BannerAdSize.MEDIUM_RECTANGLE} />
 */
const ADS_MODE: "off" | "placeholder" | "live" =
  (process.env.EXPO_PUBLIC_ADS_MODE as "off" | "placeholder" | "live" | undefined) ??
  (__DEV__ ? "placeholder" : "off");

export function AdSlot({ slot }: Props) {
  if (ADS_MODE === "off") return null;
  if (ADS_MODE === "placeholder") {
    return (
      <View
        accessible
        accessibilityLabel={`Ad slot: ${slot}`}
        className="items-center justify-center rounded-lg border border-dashed border-ink-700 bg-ink-900 px-3 py-6"
        style={{ minHeight: 90 }}
      >
        <Text className="text-[10px] font-bold uppercase tracking-wider text-text-muted">
          Sponsored
        </Text>
        <Text className="mt-1 text-[11px] text-text-muted">Ad placeholder · {slot}</Text>
      </View>
    );
  }
  return null;
}
