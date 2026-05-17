import { Link, Stack } from "expo-router";
import { useEffect, useState } from "react";
import { Pressable, Text, TextInput, View } from "react-native";

import { Screen } from "@/components/Screen";
import { api, type SearchHit } from "@/lib/api";

export default function SearchScreen() {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (q.trim().length < 2) {
      setHits([]);
      return;
    }
    setLoading(true);
    const t = setTimeout(() => {
      api<SearchHit[]>(`/api/search?q=${encodeURIComponent(q)}&limit=20`)
        .then(setHits)
        .catch(() => setHits([]))
        .finally(() => setLoading(false));
    }, 200);
    return () => clearTimeout(t);
  }, [q]);

  return (
    <Screen>
      <Stack.Screen options={{ title: "Search" }} />
      <View className="flex-row items-center gap-2 rounded-full border border-ink-700 bg-ink-900 px-4 py-2.5">
        <TextInput
          autoFocus
          value={q}
          onChangeText={setQ}
          placeholder="Search players or tournaments…"
          placeholderTextColor="#8E96A6"
          className="flex-1 text-sm text-text-primary"
          returnKeyType="search"
          autoCorrect={false}
          autoCapitalize="none"
        />
        {loading && <Text className="text-xs text-text-muted">…</Text>}
      </View>

      <View className="overflow-hidden rounded-lg border border-ink-700 bg-ink-900">
        {hits.map((h, i) => {
          const href =
            h.kind === "player"
              ? `/players/${h.slug}`
              : `/tournaments/${h.tour ?? "atp"}/${h.slug}`;
          return (
            <Link key={`${h.kind}-${h.slug}-${h.year ?? ""}`} href={href as any} asChild>
              <Pressable
                className={`flex-row items-center gap-3 px-3 py-3 ${i > 0 ? "border-t border-ink-700" : ""}`}
              >
                <View
                  className={`rounded-full px-2 py-0.5 ${
                    h.kind === "player" ? "bg-emerald-100" : "bg-amber-100"
                  }`}
                >
                  <Text
                    className={`text-[10px] font-bold uppercase tracking-wider ${
                      h.kind === "player" ? "text-emerald-800" : "text-amber-800"
                    }`}
                  >
                    {h.kind}
                  </Text>
                </View>
                <Text className="flex-1 text-sm font-medium text-text-primary" numberOfLines={1}>
                  {h.name}
                </Text>
                {h.rank && <Text className="text-xs text-text-muted">#{h.rank}</Text>}
                {h.year && <Text className="text-xs text-text-muted">{h.year}</Text>}
                {h.tour && <Text className="text-[10px] uppercase text-text-muted">{h.tour}</Text>}
              </Pressable>
            </Link>
          );
        })}
        {q.trim().length >= 2 && !loading && hits.length === 0 && (
          <Text className="px-4 py-6 text-center text-sm text-text-muted">No matches.</Text>
        )}
      </View>
    </Screen>
  );
}
