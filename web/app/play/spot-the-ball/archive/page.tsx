import Link from "next/link";

import { api, type SpotTheBallSetArchiveItem } from "@/lib/api";
import { SpotTheBallArchiveList } from "@/components/SpotTheBallArchiveList";

export const revalidate = 300;

export const metadata = {
  title: "Spot the ball · archive",
};

export default async function SpotTheBallArchivePage() {
  const sets = await api<SpotTheBallSetArchiveItem[]>(
    "/api/spot-the-ball/archive?limit=200",
    { revalidate: 300 },
  ).catch(() => [] as SpotTheBallSetArchiveItem[]);

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight">Past rounds</h1>
        <p className="text-sm text-text-secondary">
          {sets.length} {sets.length === 1 ? "round" : "rounds"} in the archive.
          Each is 5 images; play any time.
        </p>
      </header>

      <SpotTheBallArchiveList sets={sets} />

      <div>
        <Link
          href="/play/spot-the-ball"
          className="text-sm font-medium text-accent hover:text-accent-dim"
        >
          ← Back to today
        </Link>
      </div>
    </div>
  );
}
