import { Pressable, Text } from "react-native";
import Svg, { Polygon } from "react-native-svg";

import { useFollows } from "@/lib/follows";
import type { FollowKind, Tour } from "@/lib/api";

type Props = {
  kind: FollowKind;
  slug: string;
  /** Required for tournaments; ignored for players. */
  tour?: Tour | null;
  variant?: "pill" | "icon";
};

export function FollowButton({ kind, slug, tour, variant = "pill" }: Props) {
  const { isFollowing, toggle } = useFollows();
  const active = isFollowing(kind, slug, tour);

  if (variant === "icon") {
    return (
      <Pressable
        onPress={() => toggle(kind, slug, tour)}
        className={`h-9 w-9 items-center justify-center rounded-full border ${
          active ? "border-accent bg-accent" : "border-ink-700 bg-ink-900"
        }`}
        accessibilityLabel={active ? "Unfollow" : "Follow"}
      >
        <Star filled={active} color={active ? "#FFFFFF" : "#5C6473"} />
      </Pressable>
    );
  }

  return (
    <Pressable
      onPress={() => toggle(kind, slug, tour)}
      className={`flex-row items-center gap-1.5 rounded-full border px-3 py-1.5 ${
        active ? "border-accent bg-accent/10" : "border-ink-700 bg-ink-900"
      }`}
    >
      <Star filled={active} color={active ? "#16A34A" : "#5C6473"} />
      <Text className={`text-xs font-semibold ${active ? "text-accent" : "text-text-secondary"}`}>
        {active ? "Following" : "Follow"}
      </Text>
    </Pressable>
  );
}

function Star({ filled, color }: { filled: boolean; color: string }) {
  return (
    <Svg width={14} height={14} viewBox="0 0 24 24" fill={filled ? color : "none"} stroke={color} strokeWidth={2}>
      <Polygon points="12,2 15,9 22,9.5 17,14.5 18.5,22 12,18 5.5,22 7,14.5 2,9.5 9,9" />
    </Svg>
  );
}
