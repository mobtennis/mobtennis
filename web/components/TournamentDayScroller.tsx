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

  // Keep the selected chip (today, by default) centred and visible. This
  // must re-run not only when the selection changes but also when the set
  // of days changes: on the live page the day list is bootstrapped with
  // today + upcoming, then the full fetch prepends every past day. That
  // grows the row to the left of today WITHOUT changing `selectedDate`, so
  // a selection-only dependency left today crowded off to the right where
  // the user had to swipe to find it.
  const daysKey = days.map((d) => d.date).join("|");
  useEffect(() => {
    const el = selectedRef.current;
    const parent = containerRef.current;
    if (!el || !parent || parent.clientWidth === 0) return;
    // Position the chip in the scroll container's content coordinates via
    // getBoundingClientRect — `offsetLeft` is relative to the nearest
    // positioned ancestor (here the page, not this scroller), which threw
    // the centring maths off by the container's own page offset.
    const elRect = el.getBoundingClientRect();
    const parentRect = parent.getBoundingClientRect();
    const elLeft = elRect.left - parentRect.left + parent.scrollLeft;
    const elRight = elLeft + el.offsetWidth;
    const viewLeft = parent.scrollLeft;
    const viewRight = viewLeft + parent.clientWidth;
    if (elLeft < viewLeft || elRight > viewRight) {
      // Instant, not smooth: this is "keep today in view", not a gesture —
      // today should simply already be there on load, with no animated
      // swipe that reads as the very confusion we're fixing.
      parent.scrollTo({
        left: Math.max(0, elLeft - parent.clientWidth / 2 + el.offsetWidth / 2),
        behavior: "auto",
      });
    }
  }, [selectedDate, daysKey]);

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
