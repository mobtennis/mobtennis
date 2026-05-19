import { useQuery } from "@tanstack/react-query";
import { Link } from "expo-router";
import { Pressable, Text, View } from "react-native";

import { stripMarkdownLinks } from "@/components/DigestBody";
import { api, type DigestDetail } from "@/lib/api";

/**
 * Live-tab teaser linking to the full weekly digest. Renders nothing
 * when no digest has been generated yet (fresh deploy, no
 * ANTHROPIC_API_KEY), so the home screen never shows a dead section.
 */
export function DigestHomeCard() {
  const { data: digest } = useQuery({
    queryKey: ["digest-latest"],
    queryFn: () => api<DigestDetail>("/api/digests/latest"),
    // Updates Monday 06:00 UTC — 10-min stale time keeps the home
    // screen snappy without thrashing the backend.
    staleTime: 10 * 60_000,
    retry: false,
  });
  if (!digest) return null;

  // Flatten markdown links — the entire card is one tap target, so a
  // nested Link inside the lead would clobber the outer Pressable.
  const lead = stripMarkdownLinks(digest.body_md)
    .split(/(?<=\.)\s+/, 2)
    .join(" ");

  return (
    <Link href={`/digest/${digest.week_start}` as any} asChild>
      <Pressable className="rounded-lg border border-ink-700 bg-ink-900 p-4">
        <View className="flex-row items-baseline justify-between">
          <Text className="text-[10px] font-bold uppercase tracking-wider text-accent">
            This week in tennis
          </Text>
          <Text className="text-[10px] uppercase tracking-wider text-text-muted">
            {formatWeekLabel(digest.week_start)}
          </Text>
        </View>
        <Text className="mt-2 text-base font-semibold text-text-primary" numberOfLines={2}>
          {digest.headline}
        </Text>
        <Text className="mt-1 text-sm leading-6 text-text-secondary" numberOfLines={3}>
          {lead}
        </Text>
        <Text className="mt-2 text-xs font-medium text-accent">
          Read the full recap →
        </Text>
      </Pressable>
    </Link>
  );
}

function formatWeekLabel(weekStart: string): string {
  const start = new Date(`${weekStart}T00:00:00Z`);
  const end = new Date(start);
  end.setUTCDate(end.getUTCDate() + 6);
  const fmt = (d: Date) =>
    d.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
  return `${fmt(start)} – ${fmt(end)}`;
}
