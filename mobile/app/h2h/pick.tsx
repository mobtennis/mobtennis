import { useQuery } from "@tanstack/react-query";
import { Stack, router, useLocalSearchParams } from "expo-router";
import { useEffect, useRef, useState } from "react";
import { Pressable, Text, TextInput, View } from "react-native";

import { PlayerAvatar } from "@/components/PlayerAvatar";
import { Screen } from "@/components/Screen";
import { api, type PlayerDetail, type SearchHit } from "@/lib/api";

/**
 * Dedicated opponent picker. Used in two flows:
 *   - "Compare H2H" button on the player page
 *   - "Change opponent" link on the H2H card
 *
 * Pulls the anchor player detail so we can render their avatar + name
 * at the top (context cue) and tour-restrict the search. Tapping a
 * result navigates with `router.replace` so the back button skips
 * the picker and goes straight back to wherever the user came from.
 *
 * Query params:
 *   anchor — the player slug already chosen (becomes player 1 in the URL)
 *   tour   — optional ATP/WTA filter (anchor's tour). Defaults to no filter.
 */
export default function H2HPickScreen() {
  const { anchor, tour } = useLocalSearchParams<{ anchor?: string; tour?: string }>();

  const anchorQuery = useQuery({
    queryKey: ["player", anchor],
    enabled: !!anchor,
    queryFn: () => api<PlayerDetail>(`/api/players/${anchor}`),
  });

  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<TextInput>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const tourFilter = tour ?? anchorQuery.data?.tour ?? null;

  useEffect(() => {
    if (q.trim().length < 2) {
      setHits([]);
      return;
    }
    setLoading(true);
    const t = setTimeout(() => {
      api<SearchHit[]>(`/api/search?q=${encodeURIComponent(q)}&limit=30`)
        .then((all) =>
          setHits(
            all
              .filter((h) => h.kind === "player" && h.slug !== anchor)
              .filter((h) => !tourFilter || h.tour === tourFilter)
              .slice(0, 20),
          ),
        )
        .catch(() => setHits([]))
        .finally(() => setLoading(false));
    }, 200);
    return () => clearTimeout(t);
  }, [q, anchor, tourFilter]);

  if (!anchor) {
    return (
      <Screen>
        <Stack.Screen options={{ title: "Pick opponent" }} />
        <Text className="text-center text-text-muted">No player selected.</Text>
      </Screen>
    );
  }

  const a = anchorQuery.data;

  return (
    <Screen>
      <Stack.Screen options={{ title: "Pick opponent" }} />

      {a && (
        <View className="flex-row items-center gap-3 rounded-md border border-ink-700 bg-ink-900 p-3">
          <PlayerAvatar
            name={a.full_name}
            imageUrl={a.image_url}
            countryCode={a.country_code}
            size="md"
          />
          <View className="flex-1">
            <Text className="text-[10px] uppercase tracking-wider text-text-muted">
              Pick opponent for
            </Text>
            <Text className="text-base font-semibold text-text-primary" numberOfLines={1}>
              {a.full_name}
            </Text>
          </View>
          {a.tour && (
            <Text className="text-[10px] font-bold uppercase tracking-wider text-text-muted">
              {a.tour}
            </Text>
          )}
        </View>
      )}

      <View className="flex-row items-center gap-2 rounded-full border border-ink-700 bg-ink-900 px-4 py-2.5">
        <TextInput
          ref={inputRef}
          value={q}
          onChangeText={setQ}
          placeholder={tourFilter ? `Search ${tourFilter.toUpperCase()} players…` : "Search players…"}
          placeholderTextColor="#8E96A6"
          className="flex-1 text-sm text-text-primary"
          returnKeyType="search"
          autoCorrect={false}
          autoCapitalize="none"
        />
        {loading && <Text className="text-xs text-text-muted">…</Text>}
      </View>

      {hits.length > 0 && (
        <View className="overflow-hidden rounded-lg border border-ink-700 bg-ink-900">
          {hits.map((h, i) => (
            <Pressable
              key={h.slug}
              onPress={() => router.replace(`/h2h/${anchor}-vs-${h.slug}` as any)}
              className={`flex-row items-center gap-3 px-3 py-3 ${i > 0 ? "border-t border-ink-700" : ""}`}
            >
              <View className="flex-1">
                <Text className="text-sm font-medium text-text-primary" numberOfLines={1}>
                  {h.name}
                </Text>
                <View className="flex-row items-center gap-2">
                  {h.rank != null && (
                    <Text className="text-[10px] text-text-muted">#{h.rank}</Text>
                  )}
                  {h.tour && (
                    <Text className="text-[10px] uppercase tracking-wider text-text-muted">
                      {h.tour}
                    </Text>
                  )}
                </View>
              </View>
            </Pressable>
          ))}
        </View>
      )}

      {q.trim().length >= 2 && !loading && hits.length === 0 && (
        <Text className="text-center text-sm text-text-muted">No matches.</Text>
      )}
    </Screen>
  );
}
