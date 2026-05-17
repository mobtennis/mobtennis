import { useQuery } from "@tanstack/react-query";
import { Link, Stack, useLocalSearchParams } from "expo-router";
import { Pressable, Text, View } from "react-native";
import Svg, { Path } from "react-native-svg";

import { AdSlot } from "@/components/AdSlot";
import { FollowMatchButton } from "@/components/FollowMatchButton";
import { LiveDot, SuspendedDot } from "@/components/LiveDot";
import { MatchStatsPanel } from "@/components/MatchStatsPanel";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { Screen } from "@/components/Screen";
import { VideoCard } from "@/components/VideoCard";
import { api, type MatchDetail, type PlayerSummary, type VideoItemSummary } from "@/lib/api";
import { formatScore, formatSetScore, formatTime } from "@/lib/format";

export default function MatchScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { data: match, refetch, isRefetching } = useQuery({
    queryKey: ["match", id],
    enabled: !!id,
    queryFn: () => api<MatchDetail>(`/api/matches/${id}`),
    // SSE pushes match.updated events; this is just the safety net.
    refetchInterval: 60_000,
  });
  const { data: highlights = [] } = useQuery<VideoItemSummary[]>({
    queryKey: ["match-highlights", id],
    enabled: !!id,
    queryFn: () => api<VideoItemSummary[]>(`/api/videos?match_id=${id}&limit=4`),
    staleTime: 2 * 60_000,
  });

  if (!match) {
    return (
      <Screen>
        <Text className="text-center text-text-muted">Loading…</Text>
      </Screen>
    );
  }

  const sets = formatScore(match.score);
  const isLive = match.status === "live";
  const isSuspended = match.status === "suspended";
  const showGameScore = isLive;

  return (
    <Screen onRefresh={refetch} refreshing={isRefetching}>
      <Stack.Screen options={{ title: match.tournament_name }} />

      <Link href={`/tournaments/${match.tournament_tour ?? "atp"}/${match.tournament_slug}` as any} asChild>
        <Pressable>
          <Text className="text-xs font-medium text-accent">← {match.tournament_name}</Text>
        </Pressable>
      </Link>

      <View className="rounded-lg border border-ink-700 bg-ink-900 p-4">
        <View className="flex-row items-center justify-between">
          {match.round && (
            <Text className="text-xs text-text-muted">Round: {match.round}</Text>
          )}
          {isLive ? (
            <LiveDot />
          ) : isSuspended ? (
            <SuspendedDot />
          ) : (
            <Text className="text-xs uppercase tracking-wider text-text-muted">{match.status}</Text>
          )}
        </View>

        {(() => {
          const [p1Game, p2Game] = (match.current_game ?? "").split(/\s*-\s*/, 2);
          return (
            <View className="mt-4 gap-3">
              <PlayerLine
                player={match.player1}
                seed={match.player1_seed}
                sets={sets.map((s) => s.split("-")[0])}
                serving={match.server_slot === 1}
                isWinner={match.status === "finished" && match.winner_slot === 1}
                isLoser={match.status === "finished" && match.winner_slot === 2}
                gamePoints={showGameScore ? p1Game : null}
              />
              <Text className="text-center text-[10px] uppercase tracking-wider text-text-muted">vs</Text>
              <PlayerLine
                player={match.player2}
                seed={match.player2_seed}
                sets={sets.map((s) => s.split("-")[1] ?? "")}
                serving={match.server_slot === 2}
                isWinner={match.status === "finished" && match.winner_slot === 2}
                isLoser={match.status === "finished" && match.winner_slot === 1}
                gamePoints={showGameScore ? p2Game : null}
              />
            </View>
          );
        })()}

        {!isLive && !isSuspended && match.scheduled_at && (
          <Text className="mt-3 text-center text-xs text-text-muted">
            {formatTime(match.scheduled_at)}
          </Text>
        )}
        {isSuspended && (
          <Text className="mt-3 text-center text-xs italic" style={{ color: "#fbbf24cc" }}>
            Play suspended — score frozen until play resumes.
          </Text>
        )}
      </View>

      {(match.status === "live" || match.status === "suspended" || match.status === "scheduled") && (
        <FollowMatchButton matchId={match.id} />
      )}

      {match.stats && (
        <MatchStatsPanel
          stats={match.stats}
          player1={match.player1}
          player2={match.player2}
        />
      )}

      <AdSlot slot="match-mid" />

      {match.player1 && match.player2 && (
        <Link href={`/h2h/${match.player1.slug}-vs-${match.player2.slug}` as any} asChild>
          <Pressable className="rounded-md border border-ink-700 bg-ink-900 px-3 py-3">
            <Text className="text-center text-sm font-medium text-text-primary">
              Head-to-head: {match.player1.full_name} vs {match.player2.full_name}
            </Text>
          </Pressable>
        </Link>
      )}

      {highlights.length > 0 && (
        <View className="gap-2">
          <Text className="text-sm font-semibold uppercase tracking-wider text-text-muted">
            Highlights
          </Text>
          <View className="gap-2">
            {highlights.map((v) => (
              <VideoCard key={v.id} video={v} />
            ))}
          </View>
        </View>
      )}
    </Screen>
  );
}

function PlayerLine({
  player,
  seed,
  sets,
  serving,
  isWinner = false,
  isLoser = false,
  gamePoints = null,
}: {
  player: PlayerSummary | null;
  seed?: number | null;
  sets: string[];
  serving: boolean;
  isWinner?: boolean;
  isLoser?: boolean;
  gamePoints?: string | null;
}) {
  if (!player) {
    return <Text className="text-text-muted">TBD</Text>;
  }
  return (
    <Link href={`/players/${player.slug}` as any} asChild>
      <Pressable className="flex-row items-center gap-3" style={isLoser ? { opacity: 0.5 } : undefined}>
        <PlayerAvatar
          name={player.full_name}
          imageUrl={player.image_url}
          countryCode={player.country_code}
          size="md"
        />
        <View className="min-w-0 flex-1 flex-row items-center gap-2">
          {isWinner && <DetailWinnerCheck />}
          <Text
            className={`flex-1 text-base text-text-primary ${isWinner ? "font-bold" : "font-semibold"}`}
            numberOfLines={1}
          >
            {seed != null ? <Text className="text-xs font-normal text-text-muted">[{seed}] </Text> : null}
            {player.full_name}
          </Text>
          {serving && <View className="h-2 w-2 rounded-full bg-accent" />}
        </View>
        <View className="flex-row items-center gap-2">
          {sets.map((s, i) => (
            <Text key={i} className="w-6 text-right text-lg font-bold text-text-primary">
              {formatSetScore(s || "")}
            </Text>
          ))}
          {gamePoints !== null && gamePoints !== "" && (
            <>
              <View className="h-5 w-px bg-ink-700" />
              <Text className="w-8 text-right text-lg font-bold text-accent">
                {gamePoints.trim()}
              </Text>
            </>
          )}
        </View>
      </Pressable>
    </Link>
  );
}

function DetailWinnerCheck() {
  return (
    <View
      style={{
        width: 18,
        height: 18,
        borderRadius: 9,
        backgroundColor: "#16A34A",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <Svg width={11} height={11} viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth={3.5} strokeLinecap="round" strokeLinejoin="round">
        <Path d="M5 12l5 5L20 7" />
      </Svg>
    </View>
  );
}
