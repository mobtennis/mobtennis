import { Link } from "expo-router";
import { Pressable, Text, View } from "react-native";

import { PlayerAvatar } from "@/components/PlayerAvatar";
import type { LastEdition, PlayerSummary } from "@/lib/api";
import { formatScore, formatSetScore } from "@/lib/format";

export function LastEditionCard({ edition }: { edition: LastEdition }) {
  const sets = formatScore(edition.final_score).map(formatSetScore);

  return (
    <View className="overflow-hidden rounded-lg border border-ink-700 bg-ink-900">
      <View className="border-b border-ink-700 bg-ink-800 px-4 py-2">
        <Text className="text-[10px] font-bold uppercase tracking-wider text-text-muted">
          {edition.year} final
        </Text>
      </View>
      <View className="flex-row items-center gap-3 p-4">
        <View className="flex-1">
          <PlayerSide player={edition.champion} winner />
        </View>
        <Text className="text-[10px] uppercase tracking-wider text-text-muted">def.</Text>
        <View className="flex-1">
          {edition.runner_up ? (
            <PlayerSide player={edition.runner_up} winner={false} align="right" />
          ) : null}
        </View>
      </View>
      {sets.length > 0 && (
        <View className="border-t border-ink-700 bg-ink-800 px-4 py-2">
          <Text className="text-center text-sm font-semibold text-text-primary">
            {sets.join("  ")}
          </Text>
        </View>
      )}
    </View>
  );
}

function PlayerSide({
  player,
  winner,
  align = "left",
}: {
  player: PlayerSummary;
  winner: boolean;
  align?: "left" | "right";
}) {
  const right = align === "right";
  return (
    <Link href={`/players/${player.slug}` as any} asChild>
      <Pressable
        className={`flex-row items-center gap-2 ${right ? "flex-row-reverse" : ""}`}
      >
        <PlayerAvatar
          name={player.full_name}
          imageUrl={player.image_url}
          countryCode={player.country_code}
          size="md"
        />
        <View className={`min-w-0 flex-1 ${right ? "items-end" : ""}`}>
          {winner && <Text style={{ fontSize: 16 }}>🏆</Text>}
          <Text
            className="text-sm font-bold text-text-primary"
            numberOfLines={1}
          >
            {player.full_name}
          </Text>
        </View>
      </Pressable>
    </Link>
  );
}
