import { useQuery } from "@tanstack/react-query";
import { Link, Stack, useLocalSearchParams } from "expo-router";
import { Pressable, Text, View } from "react-native";

import { DigestBody } from "@/components/DigestBody";
import { Screen } from "@/components/Screen";
import { SectionHeader } from "@/components/SectionHeader";
import { api, type DigestDetail, type DigestSummary } from "@/lib/api";

export default function DigestWeekScreen() {
  const { week } = useLocalSearchParams<{ week: string }>();

  const { data: digest, refetch, isRefetching, isError } = useQuery({
    queryKey: ["digest", week],
    enabled: !!week,
    queryFn: () => api<DigestDetail>(`/api/digests/${week}`),
    retry: false,
  });
  const { data: archive = [] } = useQuery<DigestSummary[]>({
    queryKey: ["digest-archive"],
    queryFn: () => api<DigestSummary[]>("/api/digests?limit=100"),
    staleTime: 10 * 60_000,
  });

  if (isError) {
    return (
      <Screen>
        <Stack.Screen options={{ title: "Weekly digest" }} />
        <Text className="text-center text-text-muted">Digest not found.</Text>
      </Screen>
    );
  }
  if (!digest) {
    return (
      <Screen>
        <Stack.Screen options={{ title: "Weekly digest" }} />
        <Text className="text-center text-text-muted">Loading…</Text>
      </Screen>
    );
  }

  const idx = archive.findIndex((d) => d.week_start === week);
  const newer = idx > 0 ? archive[idx - 1] : null;
  const older = idx >= 0 && idx + 1 < archive.length ? archive[idx + 1] : null;

  return (
    <Screen onRefresh={refetch} refreshing={isRefetching}>
      <Stack.Screen options={{ title: "Weekly digest" }} />

      <View className="rounded-lg border border-ink-700 bg-ink-900 p-5">
        <Text className="text-[10px] font-bold uppercase tracking-wider text-accent">
          This week in tennis
        </Text>
        <Text className="mt-1 text-xs uppercase tracking-wider text-text-muted">
          {formatWeekLabel(digest.week_start)}
        </Text>
        <Text className="mt-3 text-xl font-bold text-text-primary">
          {digest.headline}
        </Text>
        {/* Plain text on mobile — no /about route exists here yet.
            When one is added, swap this for a Link/Pressable wrapper
            matching the web byline. */}
        <Text className="mt-3 text-xs text-text-muted">
          By the Mobtennis team
        </Text>
      </View>

      <View className="rounded-lg border border-ink-700 bg-ink-900 p-5">
        <DigestBody body={digest.body_md} />
      </View>

      <View className="flex-row gap-3">
        {older ? (
          <Link href={`/digest/${older.week_start}` as any} asChild>
            <Pressable className="flex-1 rounded-md border border-ink-700 bg-ink-900 px-3 py-2">
              <Text className="text-xs text-text-muted">← Previous week</Text>
              <Text className="mt-0.5 text-sm font-medium text-text-primary" numberOfLines={1}>
                {older.headline}
              </Text>
            </Pressable>
          </Link>
        ) : (
          <View className="flex-1" />
        )}
        {newer ? (
          <Link href={`/digest/${newer.week_start}` as any} asChild>
            <Pressable className="flex-1 rounded-md border border-ink-700 bg-ink-900 px-3 py-2">
              <Text className="text-right text-xs text-text-muted">Next week →</Text>
              <Text className="mt-0.5 text-right text-sm font-medium text-text-primary" numberOfLines={1}>
                {newer.headline}
              </Text>
            </Pressable>
          </Link>
        ) : (
          <View className="flex-1" />
        )}
      </View>

      {archive.length > 2 && (
        <View className="gap-2">
          <SectionHeader title="Archive" subtitle="Past weekly recaps" />
          <View className="overflow-hidden rounded-lg border border-ink-700 bg-ink-900">
            {archive.map((d, i) => (
              <Link key={d.week_start} href={`/digest/${d.week_start}` as any} asChild>
                <Pressable
                  className={`flex-row items-center gap-3 px-3 py-3 ${
                    i < archive.length - 1 ? "border-b border-ink-700" : ""
                  } ${d.week_start === week ? "bg-ink-800" : ""}`}
                >
                  <Text className="w-20 text-[11px] uppercase tracking-wider text-text-muted">
                    {formatWeekLabel(d.week_start)}
                  </Text>
                  <Text className="flex-1 text-sm font-medium text-text-primary" numberOfLines={1}>
                    {d.headline}
                  </Text>
                </Pressable>
              </Link>
            ))}
          </View>
        </View>
      )}
    </Screen>
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
