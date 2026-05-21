import { notFound } from "next/navigation";

import {
  api,
  type LiveRankingsResponse,
  type RankingsResponse,
} from "@/lib/api";
import { AdSlot } from "@/components/AdSlot";
import { RankingsLiveToggle } from "@/components/RankingsLiveToggle";
import { RankingsRow } from "@/components/RankingsRow";
import { RankingsTabs } from "@/components/RankingsTabs";
import { SectionHeader } from "@/components/SectionHeader";

export async function generateMetadata({ params }: { params: Promise<{ tour: string }> }) {
  const { tour } = await params;
  return { title: `${tour.toUpperCase()} rankings` };
}

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

export default async function RankingsPage({
  params,
  searchParams,
}: {
  params: Promise<{ tour: string }>;
  searchParams: SearchParams;
}) {
  const { tour } = await params;
  if (tour !== "atp" && tour !== "wta") notFound();

  const sp = await searchParams;
  const view = sp.view === "live" ? "live" : "official";

  // Official snapshot: cached longer since it only changes weekly.
  // Live projection: re-fetched every 5 min — backend has its own 60s
  // in-process cache so this is cheap.
  const data =
    view === "live"
      ? await api<LiveRankingsResponse>(`/api/rankings/${tour}/live?limit=200`, {
          revalidate: 300,
        }).catch(() => null)
      : await api<RankingsResponse>(`/api/rankings/${tour}?limit=200`, {
          revalidate: 3600,
        }).catch(() => null);
  if (!data) notFound();

  const subtitle =
    view === "live"
      ? "Projected — current week's earned minus defending"
      : `Week of ${new Date(data.week).toLocaleDateString()}`;

  return (
    <div className="space-y-3">
      <SectionHeader
        title={`${tour.toUpperCase()} Rankings`}
        subtitle={subtitle}
      />
      <div className="flex flex-wrap items-center gap-2">
        <RankingsTabs active={tour} />
        {/* Thin vertical divider between tour pills and view pills —
            keeps everything on one line on phones where stacking the
            two rows was eating too much vertical space. */}
        <span className="h-5 w-px shrink-0 bg-ink-700" aria-hidden />
        <RankingsLiveToggle active={view} />
      </div>

      <ul className="divide-y divide-ink-700/50 overflow-hidden rounded-lg border border-ink-700 bg-ink-900">
        {data.rows.slice(0, 25).map((row) => (
          <RankingsRow
            key={`${row.player.slug}`}
            row={row}
            live={view === "live"}
          />
        ))}
      </ul>

      {data.rows.length > 25 && <AdSlot slot="rankings-mid" />}

      {data.rows.length > 25 && (
        <ul className="divide-y divide-ink-700/50 overflow-hidden rounded-lg border border-ink-700 bg-ink-900">
          {data.rows.slice(25).map((row) => (
            <RankingsRow
              key={`${row.player.slug}`}
              row={row}
              live={view === "live"}
            />
          ))}
        </ul>
      )}
    </div>
  );
}
