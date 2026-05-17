import Link from "next/link";

import type { LastEdition } from "@/lib/api";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { formatScore, formatSetScore } from "@/lib/format";

export function LastEditionCard({ edition }: { edition: LastEdition }) {
  const sets = formatScore(edition.final_score).map(formatSetScore);

  return (
    <section className="overflow-hidden rounded-lg border border-ink-700 bg-ink-900 shadow-card">
      <div className="border-b border-ink-700 bg-ink-800/60 px-4 py-2">
        <h2 className="text-[10px] font-bold uppercase tracking-wider text-text-muted">
          {edition.year} final
        </h2>
      </div>
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 p-4">
        <PlayerSide player={edition.champion} winner />
        <div className="text-center text-[10px] uppercase tracking-wider text-text-muted">
          def.
        </div>
        {edition.runner_up ? (
          <PlayerSide player={edition.runner_up} winner={false} align="right" />
        ) : (
          <div />
        )}
      </div>
      {sets.length > 0 && (
        <div className="border-t border-ink-700 bg-ink-800/40 px-4 py-2 text-center text-sm tnum font-semibold tabular-nums">
          {sets.join("  ")}
        </div>
      )}
    </section>
  );
}

function PlayerSide({
  player,
  winner,
  align = "left",
}: {
  player: { slug: string; full_name: string; image_url: string | null; country_code: string | null };
  winner: boolean;
  align?: "left" | "right";
}) {
  return (
    <Link
      href={`/players/${player.slug}`}
      className={`flex min-w-0 items-center gap-3 ${align === "right" ? "justify-end flex-row-reverse text-right" : ""}`}
    >
      <PlayerAvatar
        name={player.full_name}
        imageUrl={player.image_url}
        countryCode={player.country_code}
        size="md"
      />
      <div className="min-w-0">
        {winner && <div className="text-base">🏆</div>}
        <div className="truncate text-sm font-bold text-text-primary">{player.full_name}</div>
      </div>
    </Link>
  );
}
