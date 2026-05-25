import { Link } from "expo-router";
import { Pressable, Text, View } from "react-native";
import Svg, { Path } from "react-native-svg";

import { LiveDot, SuspendedDot } from "@/components/LiveDot";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import type { MatchSummary, PlayerSummary } from "@/lib/api";
import { formatMatchTime, formatRound, formatScore, formatSetScore } from "@/lib/format";

export function MatchCard({ match }: { match: MatchSummary }) {
  const sets = formatScore(match.score);
  const isLive = match.status === "live";
  const isSuspended = match.status === "suspended";
  const finished = match.status === "finished";
  const round = formatRound(match.round);

  return (
    <Link href={`/matches/${match.id}` as any} asChild>
      <Pressable className="flex-row items-start gap-3 rounded-md border border-ink-700 bg-ink-900 px-3 py-2.5">
        {(() => {
          // Split "30 - 40" / "AD - 40" so each player's row gets their own
          // current-game point as a final column instead of an orphaned
          // banner under the scoreline.
          const [p1Game, p2Game] = (match.current_game ?? "").split(/\s*-\s*/, 2);
          return (
            <View className="min-w-0 flex-1 flex-col gap-1.5">
              <PlayerRow
                player={match.player1}
                sets={sets.map((s) => s.split("-")[0])}
                isServing={match.server_slot === 1}
                isWinner={finished && match.winner_slot === 1}
                isLoser={finished && match.winner_slot === 2}
                gamePoints={isLive ? p1Game : null}
              />
              <PlayerRow
                player={match.player2}
                sets={sets.map((s) => s.split("-")[1] ?? "")}
                isServing={match.server_slot === 2}
                isWinner={finished && match.winner_slot === 2}
                isLoser={finished && match.winner_slot === 1}
                gamePoints={isLive ? p2Game : null}
              />
            </View>
          );
        })()}
        <View className="items-end gap-0.5">
          {isLive ? (
            <LiveDot />
          ) : isSuspended ? (
            <SuspendedDot />
          ) : !finished ? (
            // Finished matches show no status label — the score makes it obvious.
            // Relative-day + time: "Today 18:00" / "Tomorrow 18:00" / "Wed 18:00".
            // "TBD" when api-tennis hasn't pushed the time yet (NULL scheduled_at).
            <Text className="text-xs text-text-secondary">
              {formatMatchTime(match.scheduled_at) || "TBD"}
            </Text>
          ) : null}
          {round && (
            <Text className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
              {round}
            </Text>
          )}
        </View>
      </Pressable>
    </Link>
  );
}

function PlayerRow({
  player,
  sets,
  isServing,
  isWinner = false,
  isLoser = false,
  gamePoints = null,
}: {
  player: PlayerSummary | null;
  sets: string[];
  isServing: boolean;
  isWinner?: boolean;
  isLoser?: boolean;
  gamePoints?: string | null;
}) {
  if (!player) {
    return <Text className="text-text-muted">TBD</Text>;
  }
  return (
    <View className="flex-row items-center gap-2" style={isLoser ? { opacity: 0.5 } : undefined}>
      <PlayerAvatar name={player.full_name} imageUrl={player.image_url} countryCode={player.country_code} />
      <View className="min-w-0 flex-1 flex-row items-center gap-1.5">
        {isWinner && <WinnerCheck />}
        <Text
          className={`flex-1 text-sm text-text-primary ${isWinner ? "font-bold" : "font-medium"}`}
          numberOfLines={1}
        >
          {player.full_name}
        </Text>
        {isServing && <View className="h-1.5 w-1.5 rounded-full bg-accent" />}
      </View>
      <View className="flex-row items-center gap-1.5">
        {sets.map((s, i) => (
          <Text
            key={i}
            className={`w-5 text-right text-sm text-text-primary ${isWinner ? "font-bold" : "font-semibold"}`}
          >
            {formatSetScore(s || "")}
          </Text>
        ))}
        {gamePoints !== null && gamePoints !== "" && (
          <>
            <View className="h-4 w-px bg-ink-700" />
            <Text className="w-7 text-right text-sm font-bold text-accent">
              {gamePoints.trim()}
            </Text>
          </>
        )}
      </View>
    </View>
  );
}

function WinnerCheck() {
  return (
    <View
      style={{
        width: 14,
        height: 14,
        borderRadius: 7,
        backgroundColor: "#16A34A",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <Svg width={9} height={9} viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth={3.5} strokeLinecap="round" strokeLinejoin="round">
        <Path d="M5 12l5 5L20 7" />
      </Svg>
    </View>
  );
}
