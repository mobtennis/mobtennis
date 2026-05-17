"use client";

import Link from "next/link";
import { useEffect } from "react";

import type { Tour } from "@/lib/api";
import { setPreferredTour } from "@/lib/preferred-tour";

type Props = {
  active: Tour;
  available: string[];
  /** Slug builds the per-tour href on each pill. URLs are year-less. */
  slug: string;
};

// Side effect on mount: viewing a tour-scoped tournament also implies a
// preference. So just landing on /tournaments/wta/rome sets WTA as
// your preferred tour.
export function TourPills({ active, available, slug }: Props) {
  useEffect(() => {
    setPreferredTour(active);
  }, [active]);

  if (available.length < 2) return null;

  return (
    <div className="mt-3 flex gap-1.5">
      {available.map((t) => {
        const isActive = t === active;
        return (
          <Link
            key={t}
            href={`/tournaments/${t}/${slug}`}
            scroll={false}
            className={`rounded-full border px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wider ${
              isActive
                ? "border-accent bg-accent text-white"
                : "border-ink-700 bg-ink-800 text-text-secondary hover:border-accent hover:text-accent"
            }`}
          >
            {t}
          </Link>
        );
      })}
    </div>
  );
}
