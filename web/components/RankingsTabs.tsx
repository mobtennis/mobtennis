"use client";

import Link from "next/link";
import { useEffect } from "react";

import type { Tour } from "@/lib/api";
import { setPreferredTour } from "@/lib/preferred-tour";

// Server-rendered page passes in the active tour; we mirror it into the
// preferred-tour store so other parts of the app (joint-tournament cards)
// pick this tour by default next time.
export function RankingsTabs({ active }: { active: Tour }) {
  useEffect(() => {
    setPreferredTour(active);
  }, [active]);

  return (
    <div className="flex gap-2 text-xs">
      {(["atp", "wta"] as const).map((t) => {
        const isActive = active === t;
        return (
          <Link
            key={t}
            href={`/rankings/${t}`}
            className={`rounded-full border px-3 py-1 font-medium ${
              isActive
                ? "border-accent bg-accent/15 text-accent"
                : "border-ink-700 text-text-secondary hover:text-text-primary"
            }`}
          >
            {t.toUpperCase()}
          </Link>
        );
      })}
    </div>
  );
}
