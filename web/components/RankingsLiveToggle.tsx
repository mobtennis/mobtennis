"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

/**
 * Toggle between the official weekly snapshot and the live projection.
 * Renders as two pill links so each side has a real URL and can be
 * bookmarked / shared. The active state comes from `?view=` on the
 * current path.
 */
export function RankingsLiveToggle({ active }: { active: "official" | "live" }) {
  const pathname = usePathname();
  const params = useSearchParams();

  // Build a URL that preserves any other query params and overrides view.
  const url = (view: "official" | "live") => {
    const p = new URLSearchParams(params);
    if (view === "live") p.set("view", "live");
    else p.delete("view");
    const qs = p.toString();
    return qs ? `${pathname}?${qs}` : pathname;
  };

  const pill = (label: string, kind: "official" | "live") => {
    const isActive = active === kind;
    return (
      <Link
        href={url(kind)}
        prefetch={false}
        className={`rounded-full border px-3 py-1 text-xs font-medium ${
          isActive
            ? "border-accent bg-accent/15 text-accent"
            : "border-ink-700 bg-ink-900 text-text-secondary hover:text-text-primary"
        }`}
      >
        {label}
      </Link>
    );
  };

  return (
    <div className="flex items-center gap-2">
      {pill("Official", "official")}
      {pill("Live", "live")}
    </div>
  );
}
