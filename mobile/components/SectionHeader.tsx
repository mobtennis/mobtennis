import { Link } from "expo-router";
import { Text, View } from "react-native";

export function SectionHeader({
  title,
  subtitle,
  actionHref,
  actionLabel,
}: {
  title: string;
  subtitle?: string;
  actionHref?: string;
  actionLabel?: string;
}) {
  return (
    <View className="flex-row items-end justify-between px-1 pt-1">
      <View className="min-w-0 flex-1">
        <Text className="text-base font-semibold text-text-primary">{title}</Text>
        {subtitle && <Text className="text-xs text-text-muted">{subtitle}</Text>}
      </View>
      {actionHref && (
        <Link href={actionHref as any} className="text-xs font-medium text-accent">
          {actionLabel ?? "See all"}
        </Link>
      )}
    </View>
  );
}
