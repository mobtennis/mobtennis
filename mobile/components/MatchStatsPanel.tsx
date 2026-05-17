import { Text, View } from "react-native";

import type { MatchStats, PlayerSummary } from "@/lib/api";

type Props = {
  stats: MatchStats;
  player1: PlayerSummary | null;
  player2: PlayerSummary | null;
};

export function MatchStatsPanel({ stats, player1, player2 }: Props) {
  const rows = [
    {
      label: "Service games held",
      p1Num: stats.player1.service_games_won,
      p1Den: stats.player1.service_games_played,
      p2Num: stats.player2.service_games_won,
      p2Den: stats.player2.service_games_played,
    },
    {
      label: "Break points won",
      p1Num: stats.player1.break_points_won,
      p1Den: stats.player1.break_points_total,
      p2Num: stats.player2.break_points_won,
      p2Den: stats.player2.break_points_total,
    },
    {
      label: "Total points",
      p1Num: stats.player1.points_won,
      p1Den: stats.player1.points_won + stats.player2.points_won,
      p2Num: stats.player2.points_won,
      p2Den: stats.player1.points_won + stats.player2.points_won,
    },
  ];

  return (
    <View className="rounded-lg border border-ink-700 bg-ink-900 p-4">
      <View className="mb-3 flex-row items-center justify-between">
        <Text className="flex-1 text-right text-xs font-semibold text-text-primary" numberOfLines={1}>
          {player1?.full_name ?? "Player 1"}
        </Text>
        <Text className="px-3 text-[10px] font-bold uppercase tracking-wider text-text-muted">
          stats
        </Text>
        <Text className="flex-1 text-left text-xs font-semibold text-text-primary" numberOfLines={1}>
          {player2?.full_name ?? "Player 2"}
        </Text>
      </View>
      <View className="gap-2">
        {rows.map((r) => (
          <StatRow key={r.label} {...r} />
        ))}
      </View>
    </View>
  );
}

function StatRow({
  label,
  p1Num,
  p1Den,
  p2Num,
  p2Den,
}: {
  label: string;
  p1Num: number;
  p1Den: number;
  p2Num: number;
  p2Den: number;
}) {
  const p1Pct = pct(p1Num, p1Den);
  const p2Pct = pct(p2Num, p2Den);
  const p1Label = p1Den > 0 && p1Den !== p1Num + p2Num ? `${p1Num}/${p1Den}` : String(p1Num);
  const p2Label = p2Den > 0 && p2Den !== p1Num + p2Num ? `${p2Num}/${p2Den}` : String(p2Num);

  return (
    <View>
      <View className="flex-row items-center">
        <Text className="flex-1 text-right text-xs font-semibold text-text-primary">{p1Label}</Text>
        <Text className="px-3 text-[10px] uppercase tracking-wider text-text-muted">{label}</Text>
        <Text className="flex-1 text-left text-xs font-semibold text-text-primary">{p2Label}</Text>
      </View>
      <View className="mt-1 flex-row gap-1">
        <View className="h-1.5 flex-1 overflow-hidden rounded-full bg-ink-800">
          <View
            className="ml-auto h-full bg-accent"
            style={{ width: `${p1Pct}%` }}
          />
        </View>
        <View className="h-1.5 flex-1 overflow-hidden rounded-full bg-ink-800">
          <View className="h-full bg-accent" style={{ width: `${p2Pct}%` }} />
        </View>
      </View>
    </View>
  );
}

function pct(num: number, denom: number): number {
  if (!denom) return 0;
  return Math.round((num / denom) * 100);
}
