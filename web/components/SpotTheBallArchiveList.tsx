"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { commonsImgVariant } from "@/lib/format";
import type { SpotTheBallArchiveItem } from "@/lib/api";

/**
 * Archive of every published puzzle. Each row shows the thumbnail,
 * caption, date, and (if the player has played it before) the saved
 * accuracy badge from localStorage. Client component because the
 * score badge has to read from localStorage which is browser-only.
 */

const STORAGE_KEY = "mob:stb:scores:v1";

type StoredResult = {
  date: string;
  distance_pct: number;
  band: "perfect" | "close" | "miss";
};

export function SpotTheBallArchiveList({
  items,
}: {
  items: SpotTheBallArchiveItem[];
}) {
  const [scores, setScores] = useState<Record<string, StoredResult>>({});

  useEffect(() => {
    try {
      setScores(JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}"));
    } catch {
      setScores({});
    }
  }, []);

  if (items.length === 0) {
    return (
      <p className="text-sm text-text-muted">
        No puzzles yet. The first ones land soon.
      </p>
    );
  }

  return (
    <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3">
      {items.map((it) => {
        const score = scores[it.puzzle_date];
        return (
          <li
            key={it.puzzle_date}
            className="overflow-hidden rounded-lg border border-ink-700 bg-ink-900"
          >
            <Link
              href={`/play/spot-the-ball/${it.puzzle_date}`}
              className="group block"
            >
              <div className="relative aspect-video w-full overflow-hidden bg-ink-950">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={commonsImgVariant(it.image_url, 500) ?? it.image_url}
                  alt={it.caption}
                  className="h-full w-full object-cover transition-opacity group-hover:opacity-90"
                  loading="lazy"
                />
                {score && <ScoreBadge score={score} />}
              </div>
              <div className="p-3">
                <div className="text-[10px] uppercase tracking-wider text-text-muted">
                  {it.puzzle_date}
                </div>
                <div className="mt-1 line-clamp-1 text-sm font-medium text-text-primary">
                  {it.caption}
                </div>
              </div>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}


function ScoreBadge({ score }: { score: StoredResult }) {
  const tone =
    score.band === "perfect"
      ? "bg-emerald-500/90"
      : score.band === "close"
        ? "bg-amber-500/90"
        : "bg-red-500/90";
  const label =
    score.band === "perfect"
      ? "✓ played"
      : score.band === "close"
        ? "close"
        : "missed";
  return (
    <span
      className={`absolute right-2 top-2 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white ${tone}`}
    >
      {label}
    </span>
  );
}
