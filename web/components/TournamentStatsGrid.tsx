import type { TournamentStats } from "@/lib/api";
import { surfaceColor } from "@/lib/format";

const MONTHS = [
  "", "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

export function TournamentStatsGrid({ stats }: { stats: TournamentStats }) {
  const items: { label: string; value: string; cls?: string }[] = [];
  if (stats.surface) {
    items.push({ label: "Surface", value: stats.surface, cls: surfaceColor(stats.surface) });
  }
  if (stats.indoor) items.push({ label: "Conditions", value: "Indoor" });
  if (stats.draw_size) items.push({ label: "Draw size", value: String(stats.draw_size) });
  if (stats.prize_money) {
    items.push({ label: "Prize money", value: `$${stats.prize_money.toLocaleString()}` });
  }
  if (stats.first_held) items.push({ label: "First held", value: String(stats.first_held) });
  if (stats.total_editions) {
    items.push({
      label: "Editions in our archive",
      value: String(stats.total_editions),
    });
  }
  if (stats.typical_month) {
    items.push({ label: "Typically runs in", value: MONTHS[stats.typical_month] });
  }

  if (items.length === 0) return null;

  return (
    <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3">
      {items.map((it) => (
        <div key={it.label} className="rounded-md border border-ink-700 bg-ink-900 px-3 py-2">
          <dt className="text-[10px] font-bold uppercase tracking-wider text-text-muted">
            {it.label}
          </dt>
          <dd className={`mt-0.5 text-sm font-semibold ${it.cls ?? ""}`}>{it.value}</dd>
        </div>
      ))}
    </dl>
  );
}
