import Link from "next/link";

import { api, type CallTheShotArchiveItem } from "@/lib/api";
import { CallTheShotArchiveList } from "@/components/CallTheShotArchiveList";

export const revalidate = 300;

export const metadata = {
  title: "Call the shot · archive",
};

export default async function CallTheShotArchivePage() {
  const sets = await api<CallTheShotArchiveItem[]>(
    "/api/call-the-shot/archive?limit=200",
    { revalidate: 300 },
  ).catch(() => [] as CallTheShotArchiveItem[]);

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight">Past rounds</h1>
        <p className="text-sm text-text-secondary">
          {sets.length} {sets.length === 1 ? "round" : "rounds"} in the archive.
          Each is 5 clips; play any time.
        </p>
      </header>

      <CallTheShotArchiveList sets={sets} />

      <div>
        <Link
          href="/play/call-the-shot"
          className="text-sm font-medium text-accent hover:text-accent-dim"
        >
          ← Back to today
        </Link>
      </div>
    </div>
  );
}
