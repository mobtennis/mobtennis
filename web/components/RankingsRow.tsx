import Link from "next/link";

import type { LiveRankingRow, RankingRow } from "@/lib/api";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PlayerHoverCard } from "@/components/PlayerHoverCard";
import { flagEmoji } from "@/lib/format";

type Props = {
  row: RankingRow | LiveRankingRow;
  /** If true the row uses projected_rank + delta chip. */
  live?: boolean;
};

/** Shared rendering for one player row. Re-used by official + live views.
 * Live rows show:
 *   - `projected_rank` as the primary number
 *   - a small ↑3 / ↓2 chip versus official rank
 *   - the signed weekly points delta beside the projected total. */
export function RankingsRow({ row, live = false }: Props) {
  const isLive = live && "projected_rank" in row;
  const r = isLive ? (row as LiveRankingRow) : null;
  const displayRank = r ? r.projected_rank : row.rank;
  const displayPoints = r ? r.projected_points : row.points;
  const rankDelta = r ? row.rank - r.projected_rank : 0;
  const pointsDelta = r ? r.points_change : 0;

  return (
    <li className="flex items-center gap-3 px-3 py-2.5">
      <span className="w-7 shrink-0 text-right text-sm font-bold tnum text-text-secondary">
        {displayRank}
      </span>
      {r && (
        <RankDeltaChip delta={rankDelta} />
      )}
      <PlayerAvatar
        name={row.player.full_name}
        imageUrl={row.player.image_url}
        countryCode={row.player.country_code}
      />
      <Link
        href={`/players/${row.player.slug}`}
        className="min-w-0 flex-1 truncate text-sm font-medium hover:text-accent"
      >
        <PlayerHoverCard slug={row.player.slug}>
          {row.player.full_name}
        </PlayerHoverCard>
      </Link>
      <span className="shrink-0 text-xs">{flagEmoji(row.player.country_code)}</span>
      {displayPoints !== null && displayPoints !== undefined && (
        <span className="flex shrink-0 flex-col items-end">
          <span className="w-16 text-right text-xs tnum text-text-secondary">
            {displayPoints.toLocaleString()} pts
          </span>
          {r && pointsDelta !== 0 && (
            <span
              className={`text-[10px] tnum ${
                pointsDelta > 0 ? "text-accent" : "text-live"
              }`}
            >
              {pointsDelta > 0 ? "+" : ""}
              {pointsDelta.toLocaleString()}
            </span>
          )}
        </span>
      )}
    </li>
  );
}

/** Small ↑n / ↓n chip rendered next to the rank when in live view. */
function RankDeltaChip({ delta }: { delta: number }) {
  if (delta === 0) {
    return (
      <span className="w-6 shrink-0 text-center text-[10px] text-text-muted">
        —
      </span>
    );
  }
  const up = delta > 0;
  return (
    <span
      className={`w-6 shrink-0 text-center text-[10px] font-bold tnum ${
        up ? "text-accent" : "text-live"
      }`}
    >
      {up ? "↑" : "↓"}
      {Math.abs(delta)}
    </span>
  );
}
