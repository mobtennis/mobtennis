import { Image, Text, View } from "react-native";

import { commonsImgVariant, flagEmoji } from "@/lib/format";

type Props = {
  name: string;
  imageUrl?: string | null;
  countryCode?: string | null;
  size?: "sm" | "md" | "lg";
};

const SIZE_PX = { sm: 32, md: 44, lg: 80 };
// Device-pixel target sizes for Commons thumbnails. iPhones with 3×
// retina need ~3× the CSS size to render crisply; we oversample a
// little to handle high-res tablets too.
const THUMB_PX = { sm: 96, md: 128, lg: 256 };

export function PlayerAvatar({ name, imageUrl, countryCode, size = "sm" }: Props) {
  const px = SIZE_PX[size];
  const initials = name
    .split(" ")
    .map((p) => p[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();
  // Rewrite Wikimedia full-res URLs to thumbnails. Cuts data plan
  // damage from ~5MB to ~10KB per avatar on Slam roster pages.
  const thumb = commonsImgVariant(imageUrl, THUMB_PX[size]);

  return (
    <View style={{ width: px, height: px }} className="relative shrink-0">
      <View
        style={{ width: px, height: px, borderRadius: px / 2 }}
        className="items-center justify-center overflow-hidden bg-ink-700"
      >
        {thumb ? (
          <Image source={{ uri: thumb }} style={{ width: px, height: px }} />
        ) : (
          <Text className="font-semibold text-text-primary" style={{ fontSize: px * 0.34 }}>
            {initials}
          </Text>
        )}
      </View>
      {countryCode && (
        <Text style={{ position: "absolute", right: -2, bottom: -2, fontSize: 12 }}>
          {flagEmoji(countryCode)}
        </Text>
      )}
    </View>
  );
}
