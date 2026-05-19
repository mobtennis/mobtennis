import type { H2HResponse, PlayerSummary } from "@/lib/api";
import { formatRound } from "@/lib/format";

/**
 * Editorial-grade prose summary for an H2H. Templated, not LLM-
 * generated — every sentence is derived directly from the summary
 * block. We add a paragraph of context so the page reads like
 * something a human wrote, not just a scoreboard.
 *
 * Renders nothing if there's no summary or the two players have
 * never met (the parent card already says "0 matches" in that
 * case; piling another empty paragraph on top adds nothing).
 */
export function H2HOverview({ data }: { data: H2HResponse }) {
  const s = data.summary;
  if (!s || s.total_meetings === 0) return null;

  return (
    <section className="rounded-lg border border-ink-700 bg-ink-900 p-4 shadow-card">
      <h2 className="text-[10px] font-bold uppercase tracking-wider text-text-muted">
        Overview
      </h2>
      <p className="mt-2 text-sm leading-6 text-text-secondary">
        {sentences(data, data.player1, data.player2, s).map((line, i) => (
          <span key={i}>
            {line}{" "}
          </span>
        ))}
      </p>
    </section>
  );
}

function sentences(
  data: H2HResponse,
  p1: PlayerSummary,
  p2: PlayerSummary,
  s: NonNullable<H2HResponse["summary"]>,
): string[] {
  const lines: string[] = [];

  // Opening: total meetings + span.
  if (s.span_years && s.span_years >= 1) {
    lines.push(
      `${p1.full_name} and ${p2.full_name} have met ${count(s.total_meetings, "time")} since ${s.first_meeting?.year}.`
    );
  } else if (s.first_meeting?.year) {
    lines.push(
      `${p1.full_name} and ${p2.full_name} have met ${count(s.total_meetings, "time")} so far, all in ${s.first_meeting.year}.`
    );
  } else {
    lines.push(
      `${p1.full_name} and ${p2.full_name} have met ${count(s.total_meetings, "time")} on tour.`
    );
  }

  // Lead.
  if (data.p1_wins > data.p2_wins) {
    lines.push(`${p1.full_name} leads ${data.p1_wins}–${data.p2_wins}.`);
  } else if (data.p2_wins > data.p1_wins) {
    lines.push(`${p2.full_name} leads ${data.p2_wins}–${data.p1_wins}.`);
  } else {
    lines.push(`The rivalry is level at ${data.p1_wins}–${data.p1_wins}.`);
  }

  // Finals meetings.
  if (s.finals_meetings === 1) {
    lines.push(`They've met once in a final.`);
  } else if (s.finals_meetings > 1) {
    lines.push(`They've met ${s.finals_meetings} times in a final.`);
  }

  // Surface flavour: report the surface with the largest sample, with
  // a short call-out if the split is lopsided enough to be interesting.
  const dominantSurface = dominantSurfaceLine(data, p1, p2);
  if (dominantSurface) lines.push(dominantSurface);

  // First meeting context.
  if (s.first_meeting?.tournament_name) {
    const fm = s.first_meeting;
    const winner = fm.winner_slug === p1.slug ? p1.full_name : fm.winner_slug === p2.slug ? p2.full_name : null;
    const round = formatRound(fm.round) || fm.round || "";
    const where = `at the ${fm.year} ${fm.tournament_name}`;
    if (winner) {
      lines.push(
        `Their first encounter was ${where}${round ? ` (${round})` : ""}, won by ${winner}.`
      );
    } else {
      lines.push(`Their first encounter was ${where}.`);
    }
  }

  // Most-recent meeting + current streak.
  if (s.last_meeting && s.total_meetings > 1) {
    const lm = s.last_meeting;
    const winner = lm.winner_slug === p1.slug ? p1.full_name : lm.winner_slug === p2.slug ? p2.full_name : null;
    const round = formatRound(lm.round) || lm.round || "";
    const where = lm.tournament_name ? `at the ${lm.year} ${lm.tournament_name}` : `in ${lm.year}`;
    if (winner) {
      lines.push(
        `Most recently they met ${where}${round ? ` (${round})` : ""}, with ${winner} winning.`
      );
    }
  }

  if (s.current_streak_slug && s.current_streak_count >= 2) {
    const who = s.current_streak_slug === p1.slug ? p1.full_name : s.current_streak_slug === p2.slug ? p2.full_name : null;
    if (who) {
      lines.push(`${who} has won the last ${s.current_streak_count} meetings.`);
    }
  }

  return lines;
}

function count(n: number, noun: string): string {
  return `${n} ${noun}${n === 1 ? "" : "s"}`;
}

function dominantSurfaceLine(
  data: H2HResponse,
  p1: PlayerSummary,
  p2: PlayerSummary,
): string | null {
  // Largest-sample surface, ignoring "unknown".
  const known = data.surface_splits.filter((s) => s.surface !== "unknown");
  if (!known.length) return null;
  const biggest = known.reduce((a, b) =>
    a.p1_wins + a.p2_wins >= b.p1_wins + b.p2_wins ? a : b
  );
  const total = biggest.p1_wins + biggest.p2_wins;
  if (total < 2) return null;
  const surface = biggest.surface.toLowerCase();
  // Only worth a sentence if the split is meaningfully skewed AND the
  // surface dominates the head-to-head (≥ 40% of meetings).
  if (total / Math.max(1, data.p1_wins + data.p2_wins) < 0.4) return null;
  if (biggest.p1_wins === biggest.p2_wins) {
    return `On ${surface}, they're tied ${biggest.p1_wins}–${biggest.p2_wins}.`;
  }
  const leader = biggest.p1_wins > biggest.p2_wins ? p1.full_name : p2.full_name;
  const lead = Math.max(biggest.p1_wins, biggest.p2_wins);
  const trail = Math.min(biggest.p1_wins, biggest.p2_wins);
  return `On ${surface}, ${leader} leads ${lead}–${trail}.`;
}
