import { api, type TournamentsIndexResponse } from "@/lib/api";
import { AdSlot } from "@/components/AdSlot";
import { TournamentsExplorer } from "@/components/TournamentsExplorer";

export const metadata = { title: "Tournaments" };

export default async function TournamentsIndexPage() {
  const data = await api<TournamentsIndexResponse>("/api/tournaments/index", {
    revalidate: 600,
  }).catch(() => ({ sections: [] as TournamentsIndexResponse["sections"] }));

  if (data.sections.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-ink-700 px-4 py-16 text-center">
        <p className="text-sm text-text-secondary">No tournaments to show yet.</p>
        <p className="mt-1 text-xs text-text-muted">
          The schedule populates from api-tennis on a 1-hour cycle.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">Tournaments</h1>
        <p className="mt-1 text-sm text-text-secondary">
          Every event live, upcoming, and recent — by tier.
        </p>
      </header>

      <AdSlot slot="tournaments-index-top" />

      <TournamentsExplorer data={data} />
    </div>
  );
}
