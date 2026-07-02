"use client";

import { useMemo, useState } from "react";

import type { MatchSummary } from "@/lib/api";
import { FilterableMatches } from "@/components/FilterableMatches";
import { TournamentDayScroller } from "@/components/TournamentDayScroller";
import { type FilterScope, type MatchCategory } from "@/lib/match-filters";
import {
  dayChipLabel,
  defaultSelectedDate,
  groupMatchesByDay,
} from "@/lib/tournament-days";

/**
 * Day-scroller-driven match list for big tournaments. Replaces the
 * classic "Today · N" + "Upcoming · N" pair with a single filtered
 * list that follows the selected day.
 *
 * Selection state lives here so both the scroller (top) and the
 * match list (below) re-render together as the user chips through
 * days. Default selection = today if today has matches, else most
 * recent past day (so someone opening Wimbledon at 2am UK sees
 * yesterday's results, not an empty "no matches" state).
 */

export function TournamentDayPanel({
  matches,
  year,
  visible,
  scope,
}: {
  matches: MatchSummary[];
  year: number;
  visible: MatchCategory[] | undefined;
  scope: FilterScope;
}) {
  const days = useMemo(() => groupMatchesByDay(matches), [matches]);
  const [selectedDate, setSelectedDate] = useState<string | null>(
    () => defaultSelectedDate(days),
  );

  const dayMatches = useMemo(() => {
    if (!selectedDate) return matches;
    return matches.filter(
      (m) => m.scheduled_at && m.scheduled_at.slice(0, 10) === selectedDate,
    );
  }, [matches, selectedDate]);

  const title = useMemo(() => {
    if (!selectedDate) return `Matches · ${year}`;
    return `${dayChipLabel(selectedDate)} · ${year}`;
  }, [selectedDate, year]);

  if (days.length === 0) return null;

  return (
    <div className="space-y-3">
      <TournamentDayScroller
        days={days}
        selectedDate={selectedDate}
        onSelect={setSelectedDate}
      />
      {dayMatches.length === 0 ? (
        <div className="rounded-md border border-ink-700 bg-ink-900 px-3 py-4 text-center text-sm text-text-muted">
          No matches for this day.
        </div>
      ) : (
        <FilterableMatches
          title={title}
          matches={dayMatches}
          visible={visible}
          scope={scope}
        />
      )}
    </div>
  );
}
