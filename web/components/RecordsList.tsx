import Link from "next/link";

import { PlayerAvatar } from "@/components/PlayerAvatar";
import type { TournamentRecord } from "@/lib/api";
import { flagEmoji } from "@/lib/format";

export function RecordsList({ records }: { records: TournamentRecord[] }) {
  if (records.length === 0) return null;
  return (
    <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
      {records.map((r) => (
        <li key={r.title}>
          <RecordCard record={r} />
        </li>
      ))}
    </ul>
  );
}

function RecordCard({ record }: { record: TournamentRecord }) {
  const inner = (
    <div className="flex items-center gap-3 rounded-md border border-ink-700 bg-ink-900 px-3 py-2.5 transition hover:border-ink-600 hover:bg-ink-800">
      {record.player_slug ? (
        <PlayerAvatar
          name={record.value}
          imageUrl={record.image_url}
          countryCode={record.country_code}
        />
      ) : record.country_code ? (
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-ink-700 text-base">
          {flagEmoji(record.country_code) || "🏳️"}
        </span>
      ) : null}
      <div className="min-w-0 flex-1">
        <div className="text-[10px] font-bold uppercase tracking-wider text-text-muted">
          {record.title}
        </div>
        <div className="truncate text-sm font-semibold">{record.value}</div>
        {record.detail && (
          <div className="text-[11px] text-text-muted">{record.detail}</div>
        )}
      </div>
    </div>
  );
  if (record.player_slug) {
    return <Link href={`/players/${record.player_slug}`}>{inner}</Link>;
  }
  return inner;
}
