import type { MatchStats, PlayerSummary } from "@/lib/api";

type Props = {
  stats: MatchStats;
  player1: PlayerSummary | null;
  player2: PlayerSummary | null;
};

export function MatchStatsPanel({ stats, player1, player2 }: Props) {
  const rows: { label: string; p1: string; p2: string; p1Pct: number; p2Pct: number }[] = [];

  // Service games held
  const p1HoldPct = pct(stats.player1.service_games_won, stats.player1.service_games_played);
  const p2HoldPct = pct(stats.player2.service_games_won, stats.player2.service_games_played);
  rows.push({
    label: "Service games held",
    p1: `${stats.player1.service_games_won}/${stats.player1.service_games_played}`,
    p2: `${stats.player2.service_games_won}/${stats.player2.service_games_played}`,
    p1Pct: p1HoldPct,
    p2Pct: p2HoldPct,
  });

  // Break points won (as the returner)
  const p1BpPct = pct(stats.player1.break_points_won, stats.player1.break_points_total);
  const p2BpPct = pct(stats.player2.break_points_won, stats.player2.break_points_total);
  rows.push({
    label: "Break points won",
    p1: `${stats.player1.break_points_won}/${stats.player1.break_points_total}`,
    p2: `${stats.player2.break_points_won}/${stats.player2.break_points_total}`,
    p1Pct: p1BpPct,
    p2Pct: p2BpPct,
  });

  // Total points
  const totalPts = stats.player1.points_won + stats.player2.points_won;
  rows.push({
    label: "Total points",
    p1: String(stats.player1.points_won),
    p2: String(stats.player2.points_won),
    p1Pct: pct(stats.player1.points_won, totalPts),
    p2Pct: pct(stats.player2.points_won, totalPts),
  });

  return (
    <section className="rounded-lg border border-ink-700 bg-ink-900 p-4 shadow-card">
      <div className="mb-3 grid grid-cols-[1fr_auto_1fr] items-center text-xs">
        <div className="truncate text-right font-semibold text-text-primary">
          {player1?.full_name ?? "Player 1"}
        </div>
        <div className="px-3 text-[10px] font-bold uppercase tracking-wider text-text-muted">
          stats
        </div>
        <div className="truncate text-left font-semibold text-text-primary">
          {player2?.full_name ?? "Player 2"}
        </div>
      </div>
      <div className="space-y-2">
        {rows.map((r) => (
          <StatRow key={r.label} {...r} />
        ))}
      </div>
    </section>
  );
}

function StatRow({
  label,
  p1,
  p2,
  p1Pct,
  p2Pct,
}: {
  label: string;
  p1: string;
  p2: string;
  p1Pct: number;
  p2Pct: number;
}) {
  return (
    <div>
      <div className="grid grid-cols-[1fr_auto_1fr] items-baseline text-xs">
        <div className="text-right tabular-nums font-semibold text-text-primary">{p1}</div>
        <div className="px-3 text-[10px] uppercase tracking-wider text-text-muted">{label}</div>
        <div className="text-left tabular-nums font-semibold text-text-primary">{p2}</div>
      </div>
      <div className="mt-1 grid grid-cols-2 gap-1">
        <div className="ml-auto h-1.5 w-full max-w-[140px] overflow-hidden rounded-full bg-ink-800">
          <div
            className="ml-auto h-full rounded-full bg-accent"
            style={{ width: `${p1Pct}%` }}
          />
        </div>
        <div className="mr-auto h-1.5 w-full max-w-[140px] overflow-hidden rounded-full bg-ink-800">
          <div className="h-full rounded-full bg-accent" style={{ width: `${p2Pct}%` }} />
        </div>
      </div>
    </div>
  );
}

function pct(num: number, denom: number): number {
  if (!denom) return 0;
  return Math.round((num / denom) * 100);
}
