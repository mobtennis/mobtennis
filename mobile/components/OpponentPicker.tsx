import { router } from "expo-router";
import { useEffect, useRef, useState } from "react";
import { Pressable, Text, TextInput, View } from "react-native";

import { api, type SearchHit } from "@/lib/api";

/**
 * Mobile mirror of the web OpponentPicker. Debounced /api/search →
 * navigates to /h2h/anchor-vs-newSlug on tap. Tour-filtered when a
 * tour is provided so an ATP anchor only sees ATP opponents (and
 * vice versa).
 */
export function OpponentPicker({
  anchorSlug,
  tourFilter,
  autoFocus = true,
  placeholder = "Search opponent…",
}: {
  /** Slug we're picking the opponent FOR — becomes player 1 in the new URL. */
  anchorSlug: string;
  /** Restrict results to one tour (the anchor's). */
  tourFilter?: string | null;
  autoFocus?: boolean;
  placeholder?: string;
}) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<TextInput>(null);

  useEffect(() => {
    if (autoFocus) inputRef.current?.focus();
  }, [autoFocus]);

  useEffect(() => {
    if (q.trim().length < 2) {
      setHits([]);
      return;
    }
    setLoading(true);
    const t = setTimeout(() => {
      // Over-fetch then trim — tour filter discards roughly half so
      // a 5-result-on-screen target needs headroom.
      api<SearchHit[]>(`/api/search?q=${encodeURIComponent(q)}&limit=20`)
        .then((all) =>
          setHits(
            all
              .filter((h) => h.kind === "player" && h.slug !== anchorSlug)
              .filter((h) => !tourFilter || h.tour === tourFilter)
              .slice(0, 10),
          ),
        )
        .catch(() => setHits([]))
        .finally(() => setLoading(false));
    }, 200);
    return () => clearTimeout(t);
  }, [q, anchorSlug, tourFilter]);

  return (
    <View className="w-full gap-2">
      <View className="flex-row items-center gap-2 rounded-full border border-ink-700 bg-ink-900 px-3 py-1.5">
        <TextInput
          ref={inputRef}
          value={q}
          onChangeText={setQ}
          placeholder={placeholder}
          placeholderTextColor="#8E96A6"
          className="flex-1 text-xs text-text-primary"
          returnKeyType="search"
          autoCorrect={false}
          autoCapitalize="none"
        />
        {loading && <Text className="text-[10px] text-text-muted">…</Text>}
      </View>
      {hits.length > 0 && (
        <View className="overflow-hidden rounded-md border border-ink-700 bg-ink-900">
          {hits.map((h, i) => (
            <Pressable
              key={h.slug}
              onPress={() => router.push(`/h2h/${anchorSlug}-vs-${h.slug}` as any)}
              className={`px-3 py-2 ${i > 0 ? "border-t border-ink-700" : ""}`}
            >
              <Text className="text-xs font-medium text-text-primary" numberOfLines={1}>
                {h.name}
                {h.rank != null && (
                  <Text className="text-[10px] text-text-muted"> · #{h.rank}</Text>
                )}
                {h.tour && (
                  <Text className="text-[10px] uppercase text-text-muted"> · {h.tour}</Text>
                )}
              </Text>
            </Pressable>
          ))}
        </View>
      )}
    </View>
  );
}
