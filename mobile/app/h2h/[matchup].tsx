import { useQuery } from "@tanstack/react-query";
import { Link, Redirect, Stack, useLocalSearchParams } from "expo-router";
import { Pressable, Text, View } from "react-native";

import { ChangeOpponentLink } from "@/components/ChangeOpponentLink";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { Screen } from "@/components/Screen";
import { SectionHeader } from "@/components/SectionHeader";
import { TournamentGroups } from "@/components/TournamentGroup";
import { api, type MatchSummary, type PlayerSummary } from "@/lib/api";
import { formatRound, surfaceColor } from "@/lib/format";

type H2HMeeting = {
  year: number;
  tournament_name: string | null;
  tournament_slug: string | null;
  tournament_tour: string | null;
  round: string | null;
  winner_slug: string | null;
  score: string | null;
};

type H2HSummary = {
  total_meetings: number;
  finals_meetings: number;
  span_years: number | null;
  first_meeting: H2HMeeting | null;
  last_meeting: H2HMeeting | null;
  current_streak_slug: string | null;
  current_streak_count: number;
};

type H2H = {
  player1: PlayerSummary;
  player2: PlayerSummary;
  p1_wins: number;
  p2_wins: number;
  matches: MatchSummary[];
  surface_splits: { surface: string; p1_wins: number; p2_wins: number }[];
  summary: H2HSummary | null;
};

export default function H2HScreen() {
  const { matchup } = useLocalSearchParams<{ matchup: string }>();
  const [s1, s2] = (matchup ?? "").split("-vs-", 2);
  const halfFormed = !!(matchup && matchup.includes("-vs-") && (!s1 || !s2));

  // Half-formed URL → bounce to the pick screen with the known slug
  // pre-selected. The picker fetches the player itself, so we don't
  // need to do it here. (Tour filter is omitted; the picker resolves
  // tour from the anchor record.)
  if (halfFormed) {
    const anchor = s1 || s2;
    return <Redirect href={`/h2h/pick?anchor=${anchor}` as any} />;
  }

  const { data, refetch, isRefetching } = useQuery({
    queryKey: ["h2h", matchup],
    enabled: !!matchup && matchup.includes("-vs-"),
    queryFn: () => api<H2H>(`/api/h2h/${matchup}`),
  });

  if (!data) {
    return (
      <Screen>
        <Stack.Screen options={{ title: "Head-to-head" }} />
        <Text className="text-center text-text-muted">Loading…</Text>
      </Screen>
    );
  }

  const total = data.p1_wins + data.p2_wins;
  const p1Pct = total ? (data.p1_wins / total) * 100 : 50;

  return (
    <Screen onRefresh={refetch} refreshing={isRefetching}>
      <Stack.Screen options={{ title: "Head-to-head" }} />

      <View className="rounded-lg border border-ink-700 bg-ink-900 p-4">
        <Text className="text-center text-xs uppercase tracking-wider text-text-muted">
          Head-to-head
        </Text>
        <View className="mt-3 flex-row items-start justify-between">
          {/* Each side has a "change opponent" link. Anchor passed to it
              is the OTHER player — picking under player 1 keeps player 2
              fixed and swaps player 1, and vice versa. */}
          <View className="flex-1 items-center gap-2">
            <Link href={`/players/${data.player1.slug}` as any} asChild>
              <Pressable className="items-center gap-2">
                <PlayerAvatar
                  name={data.player1.full_name}
                  imageUrl={data.player1.image_url}
                  countryCode={data.player1.country_code}
                  size="md"
                />
                <Text className="text-sm font-semibold text-text-primary" numberOfLines={1}>
                  {data.player1.full_name}
                </Text>
              </Pressable>
            </Link>
            <ChangeOpponentLink
              anchorSlug={data.player2.slug}
              tourFilter={data.player2.tour}
            />
          </View>
          <View className="flex-1 items-center">
            <Text className="text-3xl font-bold text-text-primary">
              {data.p1_wins} <Text className="text-text-muted">–</Text> {data.p2_wins}
            </Text>
            <Text className="mt-1 text-[10px] uppercase tracking-wider text-text-muted">
              {total} {total === 1 ? "match" : "matches"}
            </Text>
          </View>
          <View className="flex-1 items-center gap-2">
            <Link href={`/players/${data.player2.slug}` as any} asChild>
              <Pressable className="items-center gap-2">
                <PlayerAvatar
                  name={data.player2.full_name}
                  imageUrl={data.player2.image_url}
                  countryCode={data.player2.country_code}
                  size="md"
                />
                <Text className="text-sm font-semibold text-text-primary" numberOfLines={1}>
                  {data.player2.full_name}
                </Text>
              </Pressable>
            </Link>
            <ChangeOpponentLink
              anchorSlug={data.player1.slug}
              tourFilter={data.player1.tour}
            />
          </View>
        </View>

        <View className="mt-4 h-1.5 w-full overflow-hidden rounded-full bg-ink-700">
          <View className="h-full bg-accent" style={{ width: `${p1Pct}%` }} />
        </View>
      </View>

      {data.summary && data.summary.total_meetings > 0 && (
        <View className="rounded-lg border border-ink-700 bg-ink-900 p-4">
          <Text className="text-[10px] font-bold uppercase tracking-wider text-text-muted">
            Overview
          </Text>
          <Text className="mt-2 text-sm leading-6 text-text-secondary">
            {h2hSentences(data).join(" ")}
          </Text>
        </View>
      )}

      {data.surface_splits.length > 0 && (
        <View className="gap-2">
          <SectionHeader title="By surface" />
          <View className="gap-2">
            {data.surface_splits.map((s) => {
              const t = s.p1_wins + s.p2_wins;
              const pct = t ? (s.p1_wins / t) * 100 : 50;
              return (
                <View key={s.surface} className="rounded-md border border-ink-700 bg-ink-900 p-3">
                  <View className="flex-row items-center justify-between">
                    <Text
                      className={`text-xs font-bold uppercase tracking-wider ${surfaceColor(s.surface)}`}
                    >
                      {s.surface}
                    </Text>
                    <Text className="text-xs text-text-secondary">
                      {s.p1_wins} – {s.p2_wins}
                    </Text>
                  </View>
                  <View className="mt-2 h-1 w-full overflow-hidden rounded-full bg-ink-700">
                    <View className="h-full bg-accent" style={{ width: `${pct}%` }} />
                  </View>
                </View>
              );
            })}
          </View>
        </View>
      )}

      {data.matches.length > 0 && (
        <View className="gap-2">
          <SectionHeader title="Past meetings" />
          <TournamentGroups matches={data.matches} />
        </View>
      )}
    </Screen>
  );
}

// Sentence generator for the Overview block. Mirrors the web
// H2HOverview component — keep the two implementations in sync when
// updating the wording.
function h2hSentences(data: H2H): string[] {
  const s = data.summary;
  if (!s) return [];
  const p1 = data.player1;
  const p2 = data.player2;
  const lines: string[] = [];
  const cnt = (n: number, noun: string) => `${n} ${noun}${n === 1 ? "" : "s"}`;

  if (s.span_years && s.span_years >= 1) {
    lines.push(
      `${p1.full_name} and ${p2.full_name} have met ${cnt(s.total_meetings, "time")} since ${s.first_meeting?.year}.`,
    );
  } else if (s.first_meeting?.year) {
    lines.push(
      `${p1.full_name} and ${p2.full_name} have met ${cnt(s.total_meetings, "time")} so far, all in ${s.first_meeting.year}.`,
    );
  } else {
    lines.push(
      `${p1.full_name} and ${p2.full_name} have met ${cnt(s.total_meetings, "time")} on tour.`,
    );
  }

  if (data.p1_wins > data.p2_wins) {
    lines.push(`${p1.full_name} leads ${data.p1_wins}–${data.p2_wins}.`);
  } else if (data.p2_wins > data.p1_wins) {
    lines.push(`${p2.full_name} leads ${data.p2_wins}–${data.p1_wins}.`);
  } else {
    lines.push(`The rivalry is level at ${data.p1_wins}–${data.p1_wins}.`);
  }

  if (s.finals_meetings === 1) {
    lines.push(`They've met once in a final.`);
  } else if (s.finals_meetings > 1) {
    lines.push(`They've met ${s.finals_meetings} times in a final.`);
  }

  // Dominant surface (≥40% of meetings, lopsided enough to matter).
  const known = data.surface_splits.filter((x) => x.surface !== "unknown");
  if (known.length) {
    const biggest = known.reduce((a, b) =>
      a.p1_wins + a.p2_wins >= b.p1_wins + b.p2_wins ? a : b,
    );
    const total = biggest.p1_wins + biggest.p2_wins;
    const overall = Math.max(1, data.p1_wins + data.p2_wins);
    if (total >= 2 && total / overall >= 0.4) {
      const surface = biggest.surface.toLowerCase();
      if (biggest.p1_wins === biggest.p2_wins) {
        lines.push(`On ${surface}, they're tied ${biggest.p1_wins}–${biggest.p2_wins}.`);
      } else {
        const leader = biggest.p1_wins > biggest.p2_wins ? p1.full_name : p2.full_name;
        const lead = Math.max(biggest.p1_wins, biggest.p2_wins);
        const trail = Math.min(biggest.p1_wins, biggest.p2_wins);
        lines.push(`On ${surface}, ${leader} leads ${lead}–${trail}.`);
      }
    }
  }

  if (s.first_meeting?.tournament_name) {
    const fm = s.first_meeting;
    const winner =
      fm.winner_slug === p1.slug ? p1.full_name :
      fm.winner_slug === p2.slug ? p2.full_name : null;
    const round = formatRound(fm.round) || fm.round || "";
    const where = `at the ${fm.year} ${fm.tournament_name}`;
    if (winner) {
      lines.push(
        `Their first encounter was ${where}${round ? ` (${round})` : ""}, won by ${winner}.`,
      );
    } else {
      lines.push(`Their first encounter was ${where}.`);
    }
  }

  if (s.last_meeting && s.total_meetings > 1) {
    const lm = s.last_meeting;
    const winner =
      lm.winner_slug === p1.slug ? p1.full_name :
      lm.winner_slug === p2.slug ? p2.full_name : null;
    const round = formatRound(lm.round) || lm.round || "";
    const where = lm.tournament_name ? `at the ${lm.year} ${lm.tournament_name}` : `in ${lm.year}`;
    if (winner) {
      lines.push(
        `Most recently they met ${where}${round ? ` (${round})` : ""}, with ${winner} winning.`,
      );
    }
  }

  if (s.current_streak_slug && s.current_streak_count >= 2) {
    const who =
      s.current_streak_slug === p1.slug ? p1.full_name :
      s.current_streak_slug === p2.slug ? p2.full_name : null;
    if (who) {
      lines.push(`${who} has won the last ${s.current_streak_count} meetings.`);
    }
  }
  return lines;
}
