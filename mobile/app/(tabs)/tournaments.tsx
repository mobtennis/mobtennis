import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { ActivityIndicator, FlatList, Pressable, ScrollView, Text, View } from "react-native";

import { AdSlot } from "@/components/AdSlot";
import { Screen } from "@/components/Screen";
import { TournamentCard } from "@/components/TournamentCard";
import {
  api,
  type IndexTournament,
  type TournamentsIndexResponse,
  type TournamentsIndexSection,
} from "@/lib/api";
import { useFollows } from "@/lib/follows";

const ALL = "__all__";
const FOLLOWING = "__following__";
const PAGE_SIZE = 30;

export default function TournamentsScreen() {
  const { tournamentKeys } = useFollows();
  const [active, setActive] = useState(ALL);

  const indexQuery = useQuery({
    queryKey: ["tournaments-index"],
    queryFn: () => api<TournamentsIndexResponse>("/api/tournaments/index"),
    staleTime: 60_000,
  });
  const data = indexQuery.data;
  const baseSections = data?.sections ?? [];

  // Synthetic Following section + within-section sort that pins followed
  // tournaments to the top. Build off the index's first page only — that's
  // enough for the followed-list, and avoids fetching every section.
  const sectionsForAll = useMemo(() => {
    if (tournamentKeys.size === 0) return baseSections;
    const tk = (t: IndexTournament) => `${t.tour}/${t.slug}`;

    const followedTournaments: IndexTournament[] = [];
    const seen = new Set<string>();
    for (const s of baseSections) {
      for (const t of s.tournaments) {
        const k = tk(t);
        if (tournamentKeys.has(k) && !seen.has(k)) {
          followedTournaments.push(t);
          seen.add(k);
        }
      }
    }

    const withinSort = (a: IndexTournament, b: IndexTournament) => {
      const af = tournamentKeys.has(tk(a)) ? 0 : 1;
      const bf = tournamentKeys.has(tk(b)) ? 0 : 1;
      return af - bf;
    };

    const sortedTiers = baseSections.map((s) => ({
      ...s,
      tournaments: [...s.tournaments].sort(withinSort),
    }));

    if (followedTournaments.length === 0) return sortedTiers;
    return [
      {
        key: FOLLOWING,
        title: "Following",
        tournaments: followedTournaments,
        total: followedTournaments.length,
      },
      ...sortedTiers,
    ];
  }, [baseSections, tournamentKeys]);

  const chips = useMemo(
    () => [
      { key: ALL, title: "All" },
      ...sectionsForAll.map((s) => ({ key: s.key, title: s.title })),
    ],
    [sectionsForAll],
  );

  // Infinite scroll for single-section view. Hook must be called
  // unconditionally — `enabled` gates the fetch.
  const sectionQuery = useInfiniteQuery({
    queryKey: ["tournaments-section", active],
    enabled: active !== ALL && active !== FOLLOWING,
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      api<TournamentsIndexSection>(
        `/api/tournaments/sections/${active}?offset=${pageParam}&limit=${PAGE_SIZE}`,
      ),
    getNextPageParam: (lastPage, pages) => {
      const loaded = pages.reduce((n, p) => n + p.tournaments.length, 0);
      return loaded < lastPage.total ? loaded : undefined;
    },
    staleTime: 60_000,
  });

  if (active !== ALL && active !== FOLLOWING) {
    return (
      <SectionView
        chips={chips}
        active={active}
        setActive={setActive}
        items={sectionQuery.data?.pages.flatMap((p) => p.tournaments) ?? []}
        title={sectionQuery.data?.pages[0]?.title ?? ""}
        total={sectionQuery.data?.pages[0]?.total ?? 0}
        hasNextPage={sectionQuery.hasNextPage ?? false}
        isFetching={sectionQuery.isFetchingNextPage || sectionQuery.isLoading}
        fetchNextPage={() => {
          if (sectionQuery.hasNextPage && !sectionQuery.isFetchingNextPage) {
            sectionQuery.fetchNextPage();
          }
        }}
      />
    );
  }

  // ALL view: show first page of every section. Each section header
  // includes a "View all N →" affordance when there's more on the server.
  const visible = active === ALL
    ? sectionsForAll
    : sectionsForAll.filter((s) => s.key === active);

  return (
    <Screen onRefresh={indexQuery.refetch} refreshing={indexQuery.isRefetching}>
      <Header />
      <ChipBar chips={chips} active={active} setActive={setActive} />

      {visible.map((section, idx) => (
        <View key={section.key} className="gap-2">
          {idx === 1 && <AdSlot slot="tournaments-mid" />}
          <View className="flex-row items-baseline justify-between px-1">
            <Text className="text-base font-semibold text-text-primary">
              {section.key === FOLLOWING ? `★ ${section.title}` : section.title}
            </Text>
            <Text className="text-[11px] text-text-muted">
              {section.total} {section.total === 1 ? "event" : "events"}
            </Text>
          </View>
          <View className="gap-2">
            {section.tournaments.map((t) => (
              <TournamentCard key={`${section.key}-${t.slug}-${t.year}-${t.tour}`} t={t} />
            ))}
          </View>
          {section.total > section.tournaments.length && section.key !== FOLLOWING && (
            <Pressable onPress={() => setActive(section.key)} className="self-start py-1">
              <Text className="text-xs font-semibold text-accent">
                View all {section.total} →
              </Text>
            </Pressable>
          )}
        </View>
      ))}

      {baseSections.length === 0 && !indexQuery.isLoading && (
        <View className="rounded-lg border border-dashed border-ink-700 px-4 py-12">
          <Text className="text-center text-sm text-text-muted">No tournaments yet.</Text>
        </View>
      )}
    </Screen>
  );
}

function Header() {
  return (
    <View className="px-1">
      <Text className="text-2xl font-bold text-text-primary">Tournaments</Text>
      <Text className="mt-1 text-sm text-text-secondary">
        Every event live, upcoming, and recent — by tier.
      </Text>
    </View>
  );
}

function ChipBar({
  chips,
  active,
  setActive,
}: {
  chips: { key: string; title: string }[];
  active: string;
  setActive: (k: string) => void;
}) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={{ paddingRight: 12 }}
      className="-mx-3"
    >
      <View className="flex-row gap-2 px-3">
        {chips.map((c) => {
          const isActive = c.key === active;
          const isFollowing = c.key === FOLLOWING;
          return (
            <Pressable
              key={c.key}
              onPress={() => setActive(c.key)}
              className={`rounded-full border px-3 py-1.5 ${
                isActive ? "border-accent bg-accent/10" : "border-ink-700 bg-ink-900"
              }`}
            >
              <Text
                className={`text-xs font-semibold ${
                  isActive
                    ? "text-accent"
                    : isFollowing
                      ? "text-accent-warm"
                      : "text-text-secondary"
                }`}
              >
                {isFollowing && !isActive ? `★ ${c.title}` : c.title}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </ScrollView>
  );
}

function SectionView({
  chips,
  active,
  setActive,
  items,
  title,
  total,
  hasNextPage,
  isFetching,
  fetchNextPage,
}: {
  chips: { key: string; title: string }[];
  active: string;
  setActive: (k: string) => void;
  items: IndexTournament[];
  title: string;
  total: number;
  hasNextPage: boolean;
  isFetching: boolean;
  fetchNextPage: () => void;
}) {
  return (
    <View className="flex-1">
      <FlatList
        data={items}
        keyExtractor={(t, i) => `${t.tour}-${t.slug}-${t.year}-${i}`}
        renderItem={({ item }) => <TournamentCard t={item} />}
        ItemSeparatorComponent={() => <View style={{ height: 8 }} />}
        contentContainerStyle={{ paddingHorizontal: 12, paddingBottom: 24, gap: 8 }}
        onEndReached={fetchNextPage}
        onEndReachedThreshold={0.4}
        ListHeaderComponent={
          <View className="gap-3 pb-3 pt-2">
            <Header />
            <ChipBar chips={chips} active={active} setActive={setActive} />
            <View className="flex-row items-baseline justify-between px-1">
              <Text className="text-base font-semibold text-text-primary">{title}</Text>
              <Text className="text-[11px] text-text-muted">
                {total} {total === 1 ? "event" : "events"}
              </Text>
            </View>
          </View>
        }
        ListFooterComponent={
          isFetching ? (
            <View className="py-6">
              <ActivityIndicator />
            </View>
          ) : !hasNextPage && items.length > 0 ? (
            <View className="py-4">
              <Text className="text-center text-[11px] text-text-muted">— end —</Text>
            </View>
          ) : null
        }
      />
    </View>
  );
}
