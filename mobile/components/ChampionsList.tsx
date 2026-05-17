import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Pressable, Text, View } from "react-native";
import Svg, { Path } from "react-native-svg";

import { BracketGrid } from "@/components/Bracket";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import {
  api,
  type MatchSummary,
  type TournamentChampion,
  type Tour,
} from "@/lib/api";

const PAGE_SIZE = 5;

type Props = {
  tour: Tour;
  slug: string;
  initial: TournamentChampion[];
};

export function ChampionsList({ tour, slug, initial }: Props) {
  const [entries, setEntries] = useState(initial);
  const [offset, setOffset] = useState(initial.length);
  const [exhausted, setExhausted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [openYear, setOpenYear] = useState<number | null>(null);

  async function loadMore() {
    setLoading(true);
    try {
      const next = await api<TournamentChampion[]>(
        `/api/tournaments/${tour}/${slug}/champions?limit=${PAGE_SIZE}&offset=${offset}`,
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
        <Text className="text-center text-sm text-text-muted">No past finals on record.</Text>
      </View>
    );
  }

  return (
    <View className="gap-2">
      <View className="overflow-hidden rounded-lg border border-ink-700 bg-ink-900">
        {entries.map((c, i) => {
          const isOpen = openYear === c.year;
          return (
            <View key={c.year} className={i > 0 ? "border-t border-ink-700" : ""}>
              <Pressable
                onPress={() => setOpenYear(isOpen ? null : c.year)}
                className="flex-row items-center gap-3 px-3 py-2.5"
              >
                <Text className="w-12 text-center text-sm font-bold text-text-secondary">{c.year}</Text>
                <PlayerAvatar
                  name={c.champion.full_name}
                  imageUrl={c.champion.image_url}
                  countryCode={c.champion.country_code}
                />
                <Text className="flex-1 text-sm font-semibold text-text-primary" numberOfLines={1}>
                  {c.champion.full_name}
                </Text>
                <Text style={{ fontSize: 16 }}>🏆</Text>
                <Chevron open={isOpen} />
              </Pressable>
              {isOpen && (
                <View className="border-t border-ink-700 bg-ink-950 p-3">
                  <ChampionBracket tour={tour} slug={slug} year={c.year} />
                </View>
              )}
            </View>
          );
        })}
      </View>
      {!exhausted && (
        <Pressable
          onPress={loadMore}
          disabled={loading}
          className="rounded-md border border-ink-700 bg-ink-900 px-3 py-2"
          style={loading ? { opacity: 0.5 } : undefined}
        >
          <Text className="text-center text-xs font-semibold text-text-secondary">
            {loading ? "Loading…" : "Show earlier years"}
          </Text>
        </Pressable>
      )}
    </View>
  );
}

function Chevron({ open }: { open: boolean }) {
  return (
    <Svg
      width={14}
      height={14}
      viewBox="0 0 24 24"
      fill="none"
      stroke="#5C6473"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ transform: [{ rotate: open ? "180deg" : "0deg" }] }}
    >
      <Path d="M6 9l6 6 6-6" />
    </Svg>
  );
}

function ChampionBracket({ tour, slug, year }: { tour: Tour; slug: string; year: number }) {
  const { data: matches = [], isLoading, isError } = useQuery({
    queryKey: ["champion-bracket", tour, slug, year],
    queryFn: () => api<MatchSummary[]>(`/api/tournaments/${tour}/${slug}/${year}/matches?limit=128`),
    staleTime: 60 * 60_000,
  });

  if (isLoading) {
    return <Text className="py-2 text-center text-xs text-text-muted">Loading bracket…</Text>;
  }
  if (isError) {
    return <Text className="py-2 text-center text-xs text-text-muted">Couldn't load.</Text>;
  }
  const mainDraw = matches.filter(
    (m) => m.round && !["Q", "Q1", "Q2", "Q3"].includes(m.round.toUpperCase()),
  );
  if (mainDraw.length === 0) {
    return <Text className="py-2 text-center text-xs text-text-muted">No bracket data.</Text>;
  }
  return <BracketGrid matches={mainDraw} drawSize={null} padPlaceholders={false} />;
}
