import Link from "next/link";

import type { MatchSummary } from "@/lib/api";
import { MatchCard } from "@/components/MatchCard";
import { surfaceColor } from "@/lib/format";

type Props = {
  matches: MatchSummary[];
  showSurface?: boolean;
};

// Groups matches by tournament_slug+year and renders fotmob-style sticky headers.
export function TournamentGroups({ matches, showSurface = true }: Props) {
  const groups = new Map<string, MatchSummary[]>();
  for (const m of matches) {
    const key = `${m.tournament_slug}__${m.tournament_year}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(m);
  }

  return (
    <div className="space-y-4">
      {[...groups.entries()].map(([key, group]) => {
        const first = group[0];
        return (
          <section key={key} className="overflow-hidden rounded-lg border border-ink-700 bg-ink-900/60 shadow-card">
            <Link
              href={`/tournaments/${first.tournament_tour ?? "atp"}/${first.tournament_slug}`}
              className="flex items-center justify-between border-b border-ink-700 bg-ink-800/60 px-3 py-2 hover:bg-ink-800"
            >
              <div className="flex min-w-0 items-center gap-2">
                <span className="truncate text-sm font-semibold text-text-primary">
                  {first.tournament_name}
                </span>
                {showSurface && (
                  <span className={`text-[10px] font-bold uppercase tracking-wider ${surfaceColor(null)}`}>
                    {first.tournament_year}
                  </span>
                )}
              </div>
              <span className="text-[11px] text-text-muted">
                {group.length} match{group.length === 1 ? "" : "es"}
              </span>
            </Link>
            <div className="divide-y divide-ink-700/50">
              {group.map((m) => (
                <div key={m.id} className="bg-ink-900">
                  <MatchCard match={m} />
                </div>
              ))}
            </div>
          </section>
        );
      })}
      {groups.size === 0 && (
        <div className="rounded-lg border border-dashed border-ink-700 px-4 py-8 text-center text-text-muted">
          No matches.
        </div>
      )}
    </div>
  );
}
