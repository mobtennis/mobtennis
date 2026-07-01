import type { MatchSummary } from "@/lib/api";

/**
 * Helpers for grouping a tournament's matches into consecutive
 * "Day N" buckets. Used by the day scroller on the tournament
 * detail page and on the live page's big-tournament blocks.
 *
 * We bucket on the UTC date component of scheduled_at. Real
 * tournament days are anchored to the venue's local timezone, which
 * we don't store — UTC is a reasonable proxy for the ordinal
 * "Day N" concept especially for European/US venues where morning
 * play starts well after 00:00 UTC. Australian evening sessions
 * can drift over midnight UTC and split a venue day across two
 * chips; acceptable tradeoff to avoid per-tournament tz metadata.
 */

export type TournamentDay = {
  /** YYYY-MM-DD (UTC). */
  date: string;
  /** 1-based, in date order. */
  dayNumber: number;
  matchCount: number;
  liveCount: number;
  finishedCount: number;
  scheduledCount: number;
};


export function groupMatchesByDay(matches: MatchSummary[]): TournamentDay[] {
  const byDate = new Map<string, MatchSummary[]>();
  for (const m of matches) {
    if (!m.scheduled_at) continue;
    const date = m.scheduled_at.slice(0, 10);
    if (!byDate.has(date)) byDate.set(date, []);
    byDate.get(date)!.push(m);
  }
  const sortedDates = [...byDate.keys()].sort();
  return sortedDates.map((date, i) => {
    const dayMatches = byDate.get(date)!;
    return {
      date,
      dayNumber: i + 1,
      matchCount: dayMatches.length,
      liveCount: dayMatches.filter(
        (m) => m.status === "live" || m.status === "suspended",
      ).length,
      finishedCount: dayMatches.filter((m) => m.status === "finished").length,
      scheduledCount: dayMatches.filter((m) => m.status === "scheduled").length,
    };
  });
}


/**
 * Pick which day to open with. Rules, in order:
 *   1. Today (UTC), if it has matches.
 *   2. The most recent past day with matches (yesterday, day before, ...).
 *   3. The earliest future day with matches.
 *   4. Fall back to the first day in the list.
 */
export function defaultSelectedDate(days: TournamentDay[]): string | null {
  if (days.length === 0) return null;
  const todayUtc = new Date().toISOString().slice(0, 10);
  const exact = days.find((d) => d.date === todayUtc);
  if (exact) return exact.date;
  const past = [...days].reverse().find((d) => d.date < todayUtc);
  if (past) return past.date;
  const future = days.find((d) => d.date > todayUtc);
  if (future) return future.date;
  return days[0].date;
}


export type DayStatus = "past" | "live" | "today" | "future";

export function dayStatus(day: TournamentDay): DayStatus {
  const todayUtc = new Date().toISOString().slice(0, 10);
  if (day.liveCount > 0) return "live";
  if (day.date < todayUtc) return "past";
  if (day.date === todayUtc) return "today";
  return "future";
}


/**
 * Categories that get a day scroller. Includes Grand Slams, Finals,
 * 1000s and 500s per the operator's directive. 250s and below stay
 * on the classic today/upcoming layout — their draws are small
 * enough that a single scrollable list works.
 */
export const DAY_SCROLLER_CATEGORIES = new Set<string>([
  "grand_slam",
  "atp_finals",
  "wta_finals",
  "atp_1000",
  "wta_1000",
  "atp_500",
  "wta_500",
]);
