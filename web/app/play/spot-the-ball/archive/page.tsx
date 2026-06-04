import Link from "next/link";

import { api, type SpotTheBallArchiveItem } from "@/lib/api";
import { SpotTheBallArchiveList } from "@/components/SpotTheBallArchiveList";

export const revalidate = 300;

export const metadata = {
  title: "Spot the ball · archive",
};

export default async function SpotTheBallArchivePage() {
  const items = await api<SpotTheBallArchiveItem[]>(
    "/api/spot-the-ball/archive?limit=200",
    { revalidate: 300 },
  ).catch(() => [] as SpotTheBallArchiveItem[]);

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight">All past puzzles</h1>
        <p className="text-sm text-text-secondary">
          {items.length} {items.length === 1 ? "puzzle" : "puzzles"} in the
          archive. Played puzzles keep your score; replay any time for
          practice.
        </p>
      </header>

      <SpotTheBallArchiveList items={items} />

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
