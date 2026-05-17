import { Text, View } from "react-native";

export function Countdown({ targetDate }: { targetDate: string }) {
  const target = new Date(targetDate);
  const diffMs = target.getTime() - Date.now();
  const days = Math.ceil(diffMs / (1000 * 60 * 60 * 24));

  if (days <= 0) return null;

  const dateLabel = target.toLocaleDateString([], {
    weekday: "long",
    month: "long",
    day: "numeric",
  });

  return (
    <View className="rounded-lg border border-accent/30 bg-accent/10 p-4">
      <Text className="text-center text-[10px] font-bold uppercase tracking-wider text-accent">
        Starts in
      </Text>
      <Text className="mt-1 text-center text-3xl font-bold text-accent">
        {days}
        <Text className="text-base font-semibold"> {days === 1 ? "day" : "days"}</Text>
      </Text>
      <Text className="mt-1 text-center text-xs text-text-secondary">{dateLabel}</Text>
    </View>
  );
}
