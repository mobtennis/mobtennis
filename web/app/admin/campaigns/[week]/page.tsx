import { notFound } from "next/navigation";

import { api, type CampaignBriefsResponse } from "@/lib/api";
import { CampaignBriefCard } from "@/components/CampaignBriefCard";

export const metadata = {
  title: "Campaign briefs",
  robots: { index: false, follow: false },
};

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

export default async function CampaignBriefsPage({
  params,
  searchParams,
}: {
  params: Promise<{ week: string }>;
  searchParams: SearchParams;
}) {
  const { week } = await params;
  const sp = await searchParams;
  const key = typeof sp.key === "string" ? sp.key : undefined;
  if (!key) return <NeedsKey />;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(week)) notFound();

  const data = await api<CampaignBriefsResponse>(
    `/api/admin/campaigns/${week}?key=${encodeURIComponent(key)}`,
    { revalidate: 0 },
  ).catch(() => null);
  if (!data) return <BadKey />;

  return (
    <div className="space-y-5">
      <header>
        <div className="text-[10px] font-bold uppercase tracking-wider text-accent">
          Campaign briefs
        </div>
        <h1 className="mt-1 text-xl font-bold tracking-tight">
          {formatWeekLabel(data.week_start)}
        </h1>
        <p className="mt-1 text-sm text-text-secondary">
          {data.headline}
        </p>
      </header>

      {data.briefs.length === 0 && (
        <div className="rounded-lg border border-dashed border-ink-700 px-4 py-6 text-center text-sm text-text-muted">
          No briefs were produced for this week.
        </div>
      )}

      {data.briefs.map((b, i) => (
        <CampaignBriefCard key={i} brief={b} />
      ))}

      <footer className="rounded-md border border-ink-700 bg-ink-900 px-4 py-3 text-xs text-text-muted">
        <strong className="text-text-secondary">How to use:</strong>{" "}
        Open Google Ads → New search campaign. For each brief above,
        create one ad group with the keyword list and one Responsive Search
        Ad with the headlines + descriptions. Set the landing URL to the
        brief's path on mob.tennis. Default suggested daily budget is
        $5–$10 per campaign for 14 days; bid Maximize Clicks until you
        have conversion data.
      </footer>
    </div>
  );
}

function NeedsKey() {
  return (
    <div className="rounded-lg border border-dashed border-ink-700 px-6 py-12 text-center">
      <h1 className="text-lg font-bold">Admin key required</h1>
      <p className="mt-2 text-sm text-text-secondary">
        Append <code className="rounded bg-ink-800 px-1 py-0.5">?key=...</code>{" "}
        to the URL to view this page.
      </p>
    </div>
  );
}

function BadKey() {
  return (
    <div className="rounded-lg border border-dashed border-ink-700 px-6 py-12 text-center">
      <h1 className="text-lg font-bold">Not found</h1>
      <p className="mt-2 text-sm text-text-secondary">
        Either the admin key is wrong, or no campaign briefs exist for that
        week.
      </p>
    </div>
  );
}

function formatWeekLabel(weekStart: string): string {
  const start = new Date(`${weekStart}T00:00:00Z`);
  const end = new Date(start);
  end.setUTCDate(end.getUTCDate() + 6);
  const fmt = (d: Date) =>
    d.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
  return `${fmt(start)} – ${fmt(end)}`;
}
