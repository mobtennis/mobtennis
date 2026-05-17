import { Link } from "expo-router";
import { useState } from "react";
import { Pressable, Text, View } from "react-native";

import { api, type TournamentHistoryEntry } from "@/lib/api";
import { surfaceColor } from "@/lib/format";

const PAGE_SIZE = 10;

type Props = {
  playerSlug: string;
  initial: TournamentHistoryEntry[];
};

export function TournamentHistoryList({ playerSlug, initial }: Props) {
  const [entries, setEntries] = useState(initial);
  const [offset, setOffset] = useState(initial.length);
  const [exhausted, setExhausted] = useState(false);
  const [loading, setLoading] = useState(false);

  async function loadMore() {
    setLoading(true);
    try {
      const next = await api<TournamentHistoryEntry[]>(
        `/api/players/${playerSlug}/tournament-history?limit=${PAGE_SIZE}&offset=${offset}`,
      );
      if (next.length === 0) {
        setExhausted(true);
      } else {
        setEntries((prev) => [...prev, ...next]);
        setOffset((o) => o + next.length);
        if (next.length < PAGE_SIZE) setExhausted(true);
      }
    } catch {
      setExhausted(true);
    } finally {
      setLoading(false);
    }
  }

  if (entries.length === 0) {
    return (
      <View className="rounded-md border border-dashed border-ink-700 px-4 py-6">
        <Text className="text-center text-sm text-text-muted">No completed tournaments yet.</Text>
      </View>
    );
  }

  return (
    <View className="gap-2">
      <View className="overflow-hidden rounded-lg border border-ink-700 bg-ink-900">
        {entries.map((e, i) => (
          <Link
            key={`${e.tournament_slug}-${e.tournament_year}-${e.tournament_tour}`}
            href={`/tournaments/${e.tournament_tour}/${e.tournament_slug}` as any}
            asChild
          >
            <Pressable
              className={`flex-row items-center gap-3 px-3 py-2.5 ${i > 0 ? "border-t border-ink-700" : ""}`}
            >
              <ResultBadge result={e.result} isWinner={e.is_winner} />
              <View className="min-w-0 flex-1">
                <View className="flex-row items-center gap-2">
                  <Text className="flex-1 text-sm font-semibold text-text-primary" numberOfLines={1}>
                    {e.tournament_name}
                  </Text>
                  <Text className="text-[10px] uppercase tracking-wider text-text-muted">
                    {e.tournament_tour}
                  </Text>
                </View>
                <View className="mt-0.5 flex-row items-center gap-2">
                  <Text className="text-[11px] text-text-muted">{e.tournament_year}</Text>
                  {e.tournament_surface && (
                    <Text className={`text-[11px] ${surfaceColor(e.tournament_surface)}`}>
                      · {e.tournament_surface}
                    </Text>
                  )}
                </View>
              </View>
            </Pressable>
          </Link>
        ))}
      </View>
      {!exhausted && (
        <Pressable
          onPress={loadMore}
          disabled={loading}
          className="rounded-md border border-ink-700 bg-ink-900 px-3 py-2"
          style={loading ? { opacity: 0.5 } : undefined}
        >
          <Text className="text-center text-xs font-semibold text-text-secondary">
            {loading ? "Loading…" : "Show more"}
          </Text>
        </Pressable>
      )}
    </View>
  );
}

function ResultBadge({ result, isWinner }: { result: string; isWinner: boolean }) {
  let bg = "bg-ink-800";
  let fg = "text-text-secondary";
  if (isWinner) {
    bg = "bg-amber-100";
    fg = "text-amber-800";
  } else if (result === "F") {
    bg = "bg-rose-100";
    fg = "text-rose-800";
  } else if (result === "SF") {
    bg = "bg-fuchsia-100";
    fg = "text-fuchsia-800";
  } else if (result === "QF") {
    bg = "bg-sky-100";
    fg = "text-sky-800";
  }
  return (
    <View className={`h-7 w-12 items-center justify-center rounded-md ${bg}`}>
      <Text className={`text-[11px] font-bold ${fg}`}>
        {isWinner ? "🏆 W" : result}
      </Text>
    </View>
  );
}
