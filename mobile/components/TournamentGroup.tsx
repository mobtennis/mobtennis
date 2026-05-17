import { Link } from "expo-router";
import { Pressable, Text, View } from "react-native";

import { MatchCard } from "@/components/MatchCard";
import type { MatchSummary } from "@/lib/api";

export function TournamentGroups({ matches }: { matches: MatchSummary[] }) {
  const groups = new Map<string, MatchSummary[]>();
  for (const m of matches) {
    const key = `${m.tournament_slug}__${m.tournament_year}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(m);
  }

  if (groups.size === 0) {
    return (
      <View className="rounded-md border border-dashed border-ink-700 px-4 py-8">
        <Text className="text-center text-text-muted">No matches.</Text>
      </View>
    );
  }

  return (
    <View className="gap-4">
      {[...groups.entries()].map(([key, group]) => {
        const first = group[0];
        return (
          <View key={key} className="overflow-hidden rounded-lg border border-ink-700 bg-ink-900">
            <Link href={`/tournaments/${first.tournament_tour ?? "atp"}/${first.tournament_slug}` as any} asChild>
              <Pressable className="flex-row items-center justify-between border-b border-ink-700 bg-ink-800 px-3 py-2">
                <Text className="flex-1 text-sm font-semibold text-text-primary" numberOfLines={1}>
                  {first.tournament_name}
                </Text>
                <Text className="text-[11px] text-text-muted">
                  {group.length} {group.length === 1 ? "match" : "matches"}
                </Text>
              </Pressable>
            </Link>
            <View className="gap-px">
              {group.map((m) => (
                <View key={m.id}>
                  <MatchCard match={m} />
                </View>
              ))}
            </View>
          </View>
        );
      })}
    </View>
  );
}
