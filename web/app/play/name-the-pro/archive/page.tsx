import Link from "next/link";

import { api, type NameTheProArchiveItem } from "@/lib/api";
import { NameTheProArchiveList } from "@/components/NameTheProArchiveList";

export const revalidate = 300;

export const metadata = {
  title: "Name the pro · archive",
};

export default async function NameTheProArchivePage() {
  const sets = await api<NameTheProArchiveItem[]>(
    "/api/name-the-pro/archive?limit=200",
    { revalidate: 300 },
  ).catch(() => [] as NameTheProArchiveItem[]);

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight">Past rounds</h1>
        <p className="text-sm text-text-secondary">
          {sets.length} {sets.length === 1 ? "round" : "rounds"} in the archive.
          Each is 5 images; play any time.
        </p>
      </header>

      <NameTheProArchiveList sets={sets} />

      <div>
        <Link
          href="/play/name-the-pro"
          className="text-sm font-medium text-accent hover:text-accent-dim"
        >
          ← Back to today
        </Link>
      </div>
    </div>
  );
}
