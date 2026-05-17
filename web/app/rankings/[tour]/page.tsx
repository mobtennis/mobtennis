import Link from "next/link";
import { notFound } from "next/navigation";

import { api, type RankingsResponse } from "@/lib/api";
import { AdSlot } from "@/components/AdSlot";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { RankingsTabs } from "@/components/RankingsTabs";
import { SectionHeader } from "@/components/SectionHeader";
import { flagEmoji } from "@/lib/format";

export async function generateMetadata({ params }: { params: Promise<{ tour: string }> }) {
  const { tour } = await params;
  return { title: `${tour.toUpperCase()} rankings` };
}

export default async function RankingsPage({ params }: { params: Promise<{ tour: string }> }) {
  const { tour } = await params;
  if (tour !== "atp" && tour !== "wta") notFound();

  const data = await api<RankingsResponse>(`/api/rankings/${tour}?limit=200`).catch(() => null);
  if (!data) notFound();

  return (
    <div className="space-y-3">
      <SectionHeader
        title={`${tour.toUpperCase()} Rankings`}
        subtitle={`Week of ${new Date(data.week).toLocaleDateString()}`}
      />
      <RankingsTabs active={tour} />

      <ul className="divide-y divide-ink-700/50 overflow-hidden rounded-lg border border-ink-700 bg-ink-900">
        {data.rows.slice(0, 25).map((row) => (
          <li key={`${row.rank}-${row.player.slug}`} className="flex items-center gap-3 px-3 py-2.5">
            <span className="w-7 shrink-0 text-right text-sm font-bold tnum text-text-secondary">{row.rank}</span>
            <PlayerAvatar
              name={row.player.full_name}
              imageUrl={row.player.image_url}
              countryCode={row.player.country_code}
            />
            <Link href={`/players/${row.player.slug}`} className="min-w-0 flex-1 truncate text-sm font-medium hover:text-accent">
              {row.player.full_name}
            </Link>
            <span className="shrink-0 text-xs">{flagEmoji(row.player.country_code)}</span>
            {row.points && <span className="w-16 shrink-0 text-right text-xs tnum text-text-secondary">{row.points.toLocaleString()} pts</span>}
          </li>
        ))}
      </ul>

      {data.rows.length > 25 && <AdSlot slot="rankings-mid" />}

      {data.rows.length > 25 && (
        <ul className="divide-y divide-ink-700/50 overflow-hidden rounded-lg border border-ink-700 bg-ink-900">
          {data.rows.slice(25).map((row) => (
            <li key={`${row.rank}-${row.player.slug}`} className="flex items-center gap-3 px-3 py-2.5">
              <span className="w-7 shrink-0 text-right text-sm font-bold tnum text-text-secondary">{row.rank}</span>
              <PlayerAvatar
                name={row.player.full_name}
                imageUrl={row.player.image_url}
                countryCode={row.player.country_code}
              />
              <Link href={`/players/${row.player.slug}`} className="min-w-0 flex-1 truncate text-sm font-medium hover:text-accent">
                {row.player.full_name}
              </Link>
              <span className="shrink-0 text-xs">{flagEmoji(row.player.country_code)}</span>
              {row.points && <span className="w-16 shrink-0 text-right text-xs tnum text-text-secondary">{row.points.toLocaleString()} pts</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
