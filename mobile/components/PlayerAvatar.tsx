import { Image, Text, View } from "react-native";

import { flagEmoji } from "@/lib/format";

type Props = {
  name: string;
  imageUrl?: string | null;
  countryCode?: string | null;
  size?: "sm" | "md" | "lg";
};

const SIZE_PX = { sm: 32, md: 44, lg: 80 };

export function PlayerAvatar({ name, imageUrl, countryCode, size = "sm" }: Props) {
  const px = SIZE_PX[size];
  const initials = name
    .split(" ")
    .map((p) => p[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <View style={{ width: px, height: px }} className="relative shrink-0">
      <View
        style={{ width: px, height: px, borderRadius: px / 2 }}
        className="items-center justify-center overflow-hidden bg-ink-700"
      >
        {imageUrl ? (
          <Image source={{ uri: imageUrl }} style={{ width: px, height: px }} />
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
