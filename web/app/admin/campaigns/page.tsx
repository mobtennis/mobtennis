import { redirect } from "next/navigation";

import { api, type CampaignBriefsResponse } from "@/lib/api";

export const metadata = {
  title: "Campaign briefs",
  robots: { index: false, follow: false },
};

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

/** Bounces to the latest week's briefs. Preserves the `?key=` param so
 * the admin-gate dependency on the underlying endpoint still passes. */
export default async function CampaignsIndex({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const sp = await searchParams;
  const key = typeof sp.key === "string" ? sp.key : undefined;
  if (!key) {
    return (
      <div className="rounded-lg border border-dashed border-ink-700 px-6 py-12 text-center">
        <h1 className="text-lg font-bold">Admin key required</h1>
        <p className="mt-2 text-sm text-text-secondary">
          Append <code className="rounded bg-ink-800 px-1 py-0.5">?key=...</code>{" "}
          to the URL.
        </p>
      </div>
    );
  }

  const latest = await api<CampaignBriefsResponse>(
    `/api/admin/campaigns/latest?key=${encodeURIComponent(key)}`,
    { revalidate: 0 },
  ).catch(() => null);
  if (!latest) {
    return (
      <div className="rounded-lg border border-dashed border-ink-700 px-6 py-12 text-center">
        <h1 className="text-lg font-bold">No briefs yet</h1>
        <p className="mt-2 text-sm text-text-secondary">
          Either the admin key is wrong or no digest with campaign briefs has
          been generated yet.
        </p>
      </div>
    );
  }
  redirect(`/admin/campaigns/${latest.week_start}?key=${encodeURIComponent(key)}`);
}
