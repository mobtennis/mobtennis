"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import type { NameTheProArchiveItem } from "@/lib/api";

/**
 * Client island for the NTP archive grid. Reads localStorage to surface
 * the player's score on each set they've already finished, plus a
 * compact correct/wrong pattern strip.
 */

type SavedSummary = {
  set_id: number;
  total_points: number;
  results: Array<{ is_correct: boolean }>;
  completed_at: string;
};

const SET_KEY_PREFIX = "mob:ntp:set:";
const POINTS_PER_CORRECT = 100;


function loadAllSummaries(): Record<number, SavedSummary> {
  if (typeof window === "undefined") return {};
  const out: Record<number, SavedSummary> = {};
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (!key || !key.startsWith(SET_KEY_PREFIX)) continue;
    try {
      const value = JSON.parse(localStorage.getItem(key) || "");
      if (value && typeof value.set_id === "number") {
        out[value.set_id] = value;
      }
    } catch {
      /* skip malformed entries */
    }
  }
  return out;
}


export function NameTheProArchiveList({
  sets,
}: {
  sets: NameTheProArchiveItem[];
}) {
  const [summaries, setSummaries] = useState<Record<number, SavedSummary>>({});

  useEffect(() => {
    setSummaries(loadAllSummaries());
  }, []);

  if (sets.length === 0) {
    return (
      <p className="text-sm text-text-muted">No rounds yet — check back soon.</p>
    );
  }

  return (
    <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3">
      {sets.map((s) => {
        const summary = summaries[s.id];
        return (
          <li
            key={s.id}
            className="overflow-hidden rounded-lg border border-ink-700 bg-ink-900"
          >
            <Link href={`/play/name-the-pro/sets/${s.id}`} className="group block">
              <div className="relative aspect-video w-full overflow-hidden bg-ink-950">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={s.cover_image_url}
                  alt={s.title ?? `Round ${s.id}`}
                  className="h-full w-full object-cover transition-opacity group-hover:opacity-90"
                  loading="lazy"
                />
                {summary && (
                  <ScoreBadge
                    summary={summary}
                    max={s.image_count * POINTS_PER_CORRECT}
                  />
                )}
              </div>
              <div className="p-3">
                <div className="text-[10px] uppercase tracking-wider text-text-muted">
                  {s.publish_date} · {s.image_count} images
                </div>
                <div className="mt-1 line-clamp-1 text-sm font-medium text-text-primary">
                  {s.title ?? `Round ${s.id}`}
                </div>
                {summary && <PatternRow summary={summary} />}
              </div>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}


function ScoreBadge({
  summary,
  max,
}: {
  summary: SavedSummary;
  max: number;
}) {
  return (
    <span className="absolute right-2 top-2 rounded-full bg-emerald-600/95 px-2.5 py-1 text-xs font-bold text-white shadow-lg">
      ✓ {summary.total_points}/{max}
    </span>
  );
}


function PatternRow({ summary }: { summary: SavedSummary }) {
  return (
    <div className="mt-1.5 flex gap-1">
      {summary.results.map((r, i) => {
        const bg = r.is_correct ? "bg-emerald-500" : "bg-red-500";
        return <span key={i} className={`h-2.5 w-2.5 rounded-sm ${bg}`} />;
      })}
    </div>
  );
}
