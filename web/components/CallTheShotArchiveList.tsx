"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import type { CallTheShotArchiveItem } from "@/lib/api";

type SavedSummary = {
  set_id: number;
  total_points: number;
  results: Array<{ is_correct: boolean }>;
  completed_at: string;
};

const SET_KEY_PREFIX = "mob:cts:set:";
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
    } catch { /* skip malformed entries */ }
  }
  return out;
}


export function CallTheShotArchiveList({
  sets,
}: {
  sets: CallTheShotArchiveItem[];
}) {
  const [summaries, setSummaries] = useState<Record<number, SavedSummary>>({});
  useEffect(() => { setSummaries(loadAllSummaries()); }, []);

  if (sets.length === 0) {
    return <p className="text-sm text-text-muted">No rounds yet — check back soon.</p>;
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
            <Link href={`/play/call-the-shot/sets/${s.id}`} className="group block">
              <div className="p-3">
                <div className="text-[10px] uppercase tracking-wider text-text-muted">
                  {s.publish_date} · {s.item_count} clips
                </div>
                <div className="mt-1 line-clamp-1 text-sm font-medium text-text-primary">
                  {s.title ?? `Round ${s.id}`}
                </div>
                {summary && (
                  <>
                    <div className="mt-1.5 text-xs font-semibold text-emerald-700">
                      ✓ {summary.total_points} / {s.item_count * POINTS_PER_CORRECT}
                    </div>
                    <div className="mt-1.5 flex gap-1">
                      {summary.results.map((r, i) => (
                        <span
                          key={i}
                          className={`h-2.5 w-2.5 rounded-sm ${r.is_correct ? "bg-emerald-500" : "bg-red-500"}`}
                        />
                      ))}
                    </div>
                  </>
                )}
              </div>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
