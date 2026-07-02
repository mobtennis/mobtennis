"use client";

import { useEffect, useRef } from "react";

import {
  dayChipLabel,
  dayStatus,
  type TournamentDay,
} from "@/lib/tournament-days";

/**
 * Horizontal row of "Day N" chips for a big tournament. Pure UI —
 * ownership of `selectedDate` lives with the parent client component
 * (TournamentDayPanel or the live-page block).
 */

export function TournamentDayScroller({
  days,
  selectedDate,
  onSelect,
}: {
  days: TournamentDay[];
  selectedDate: string | null;
  onSelect: (date: string) => void;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const selectedRef = useRef<HTMLButtonElement | null>(null);

  // Scroll the selected chip into view on mount / when it changes,
  // so opening the page on a Slam Day 5 lands you on the right chip
  // instead of Day 1 off-screen to the left.
  useEffect(() => {
    if (!selectedRef.current || !containerRef.current) return;
    const el = selectedRef.current;
    const parent = containerRef.current;
    const elLeft = el.offsetLeft;
    const elRight = elLeft + el.offsetWidth;
    const viewLeft = parent.scrollLeft;
    const viewRight = viewLeft + parent.clientWidth;
    if (elLeft < viewLeft || elRight > viewRight) {
      parent.scrollTo({
        left: Math.max(0, elLeft - parent.clientWidth / 2 + el.offsetWidth / 2),
        behavior: "smooth",
      });
    }
  }, [selectedDate]);

  if (days.length <= 1) return null;

  return (
    <div
      ref={containerRef}
      className="scrollbar-thin -mx-1 overflow-x-auto overscroll-x-contain px-1"
    >
      <div className="flex gap-1.5">
        {days.map((day) => {
          const status = dayStatus(day);
          const isSelected = day.date === selectedDate;
          const tone = isSelected
            ? "border-accent bg-accent text-white"
            : status === "live"
              ? "border-emerald-500/50 bg-emerald-500/10 text-emerald-700 hover:bg-emerald-500/20"
              : status === "past"
                ? "border-ink-700 bg-ink-900 text-text-muted hover:bg-ink-800"
                : "border-ink-700 bg-ink-900 text-text-secondary hover:bg-ink-800";
          return (
            <button
              key={day.date}
              ref={isSelected ? selectedRef : undefined}
              type="button"
              onClick={() => onSelect(day.date)}
              className={`shrink-0 rounded-md border px-2.5 py-1 text-xs font-semibold whitespace-nowrap transition ${tone}`}
              aria-current={isSelected ? "true" : undefined}
            >
              {dayChipLabel(day.date)}
            </button>
          );
        })}
      </div>
    </div>
  );
}
