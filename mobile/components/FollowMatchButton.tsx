import { useState } from "react";
import { Modal, Pressable, Text, View } from "react-native";
import Svg, { Polygon } from "react-native-svg";

import type { MatchFollowGranularity } from "@/lib/api";
import { useMatchFollows } from "@/lib/match-follows";
import { registerForPushNotifications } from "@/lib/push";

type Props = {
  matchId: number;
  /** When true, render a compact icon-only button (for match cards). */
  compact?: boolean;
};

export function FollowMatchButton({ matchId, compact = false }: Props) {
  const { getGranularity, follow, unfollow } = useMatchFollows();
  const [pickerOpen, setPickerOpen] = useState(false);
  const granularity = getGranularity(matchId);
  const active = granularity !== null;

  async function onPress() {
    if (active) {
      unfollow(matchId);
      return;
    }
    // First follow on this device → make sure we're registered for push.
    // No-op if already done; cheap to call repeatedly.
    await registerForPushNotifications();
    setPickerOpen(true);
  }

  function pick(g: MatchFollowGranularity) {
    follow(matchId, g);
    setPickerOpen(false);
  }

  if (compact) {
    return (
      <>
        <Pressable
          onPress={onPress}
          hitSlop={8}
          accessibilityLabel={active ? "Unfollow match" : "Follow match"}
        >
          <Bell filled={active} color={active ? "#16A34A" : "#5C6473"} />
        </Pressable>
        <GranularityPicker
          open={pickerOpen}
          onClose={() => setPickerOpen(false)}
          onPick={pick}
        />
      </>
    );
  }

  return (
    <>
      <Pressable
        onPress={onPress}
        className={`flex-row items-center justify-center gap-2 rounded-full border px-4 py-2 ${
          active ? "border-accent bg-accent/10" : "border-ink-700 bg-ink-900"
        }`}
      >
        <Bell filled={active} color={active ? "#16A34A" : "#5C6473"} />
        <Text className={`text-sm font-semibold ${active ? "text-accent" : "text-text-secondary"}`}>
          {active
            ? granularity === "every_game" ? "Notifying every game" : "Notifying key moments"
            : "Follow match"}
        </Text>
      </Pressable>
      <GranularityPicker
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onPick={pick}
      />
    </>
  );
}

function GranularityPicker({
  open,
  onClose,
  onPick,
}: {
  open: boolean;
  onClose: () => void;
  onPick: (g: MatchFollowGranularity) => void;
}) {
  return (
    <Modal visible={open} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable onPress={onClose} className="flex-1 items-center justify-center bg-black/40 px-6">
        <Pressable className="w-full max-w-sm rounded-lg border border-ink-700 bg-ink-900 p-4">
          <Text className="text-base font-bold text-text-primary">Notify me on</Text>
          <Text className="mt-1 text-xs text-text-muted">
            We'll stop automatically when the match ends.
          </Text>
          <View className="mt-3 gap-2">
            <Choice
              title="Key moments"
              subtitle="Match start, sets, breaks of serve, tiebreaks, finish"
              onPress={() => onPick("key_moments")}
            />
            <Choice
              title="Every game"
              subtitle="A ping after every completed game"
              onPress={() => onPick("every_game")}
            />
          </View>
          <Pressable
            onPress={onClose}
            className="mt-3 rounded-md border border-ink-700 px-3 py-2"
          >
            <Text className="text-center text-sm font-semibold text-text-secondary">Cancel</Text>
          </Pressable>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

function Choice({ title, subtitle, onPress }: { title: string; subtitle: string; onPress: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      className="rounded-md border border-ink-700 bg-ink-800 px-3 py-3"
    >
      <Text className="text-sm font-bold text-text-primary">{title}</Text>
      <Text className="mt-0.5 text-xs text-text-muted">{subtitle}</Text>
    </Pressable>
  );
}

function Bell({ filled, color }: { filled: boolean; color: string }) {
  return (
    <Svg width={16} height={16} viewBox="0 0 24 24" fill={filled ? color : "none"} stroke={color} strokeWidth={2}>
      <Polygon points="12,3 18,10 18,16 20,18 4,18 6,16 6,10" />
      <Polygon points="10,18 10,20 14,20 14,18" />
    </Svg>
  );
}
