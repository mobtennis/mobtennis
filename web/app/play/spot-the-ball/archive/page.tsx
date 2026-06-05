import Link from "next/link";

import { api, type SpotTheBallSetArchiveItem } from "@/lib/api";
import { SectionHeader } from "@/components/SectionHeader";

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

      {sets.length === 0 ? (
        <p className="text-sm text-text-muted">No rounds yet — check back soon.</p>
      ) : (
        <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3">
          {sets.map((s) => (
            <li
              key={s.id}
              className="overflow-hidden rounded-lg border border-ink-700 bg-ink-900"
            >
              <Link href={`/play/spot-the-ball/sets/${s.id}`} className="group block">
                <div className="relative aspect-video w-full overflow-hidden bg-ink-950">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={s.cover_image_url}
                    alt={s.title ?? `Round ${s.id}`}
                    className="h-full w-full object-cover transition-opacity group-hover:opacity-90"
                    loading="lazy"
                  />
                </div>
                <div className="p-3">
                  <div className="text-[10px] uppercase tracking-wider text-text-muted">
                    {s.publish_date} · {s.image_count} images
                  </div>
                  <div className="mt-1 line-clamp-1 text-sm font-medium text-text-primary">
                    {s.title ?? `Round ${s.id}`}
                  </div>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}

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
