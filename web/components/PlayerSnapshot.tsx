import Link from "next/link";

import type { PlayerSnapshot as Snapshot } from "@/lib/api";

/**
 * Editorial paragraph summarising a player's career. Templated, not
 * LLM-generated — every sentence is derived from the snapshot data.
 *
 * Renders nothing when the player has no decisive history we can
 * meaningfully say something about (e.g., zero matches, all losses,
 * etc. — usually means a junior or wildcard entry without enough
 * data on file).
 */
export function PlayerSnapshot({ snapshot }: { snapshot: Snapshot | null }) {
  if (!snapshot) return null;
  const total = snapshot.career_wins + snapshot.career_losses;
  if (total < 5) return null;

  return (
    <section className="rounded-lg border border-ink-700 bg-ink-900 p-4 shadow-card">
      <h2 className="text-[10px] font-bold uppercase tracking-wider text-text-muted">
        Career snapshot
      </h2>
      <p className="mt-2 text-sm leading-6 text-text-secondary">
        {sentences(snapshot).map((line, i) => (
          <span key={i}>{line} </span>
        ))}
      </p>
    </section>
  );
}

function sentences(s: Snapshot): React.ReactNode[] {
  const lines: React.ReactNode[] = [];
  const total = s.career_wins + s.career_losses;
  const winPct = total ? Math.round((s.career_wins / total) * 100) : 0;

  // Opening: career record + winrate.
  lines.push(
    `${s.full_name} has a career singles record of ${s.career_wins}–${s.career_losses} (${winPct}% wins)`
    + (s.career_titles > 0
      ? `, with ${s.career_titles} title${s.career_titles === 1 ? "" : "s"} from ${s.career_finals} final${s.career_finals === 1 ? "" : "s"}.`
      : `.`)
  );

  // Slam history.
  if (s.slam_titles > 0 && s.best_slam) {
    const b = s.best_slam;
    lines.push(
      <>
        {s.slam_titles} of those {s.career_titles === s.slam_titles ? "are" : "titles came at"} Grand Slams; the most recent was the{" "}
        <Link
          href={`/tournaments/${b.tournament_tour}/${b.tournament_slug}`}
          className="text-accent underline decoration-dotted underline-offset-4 hover:text-accent-dim"
        >
          {b.year} {b.tournament_name}
        </Link>
        {b.final_opponent_name ? ` over ${b.final_opponent_name}` : ""}
        {b.final_score ? ` (${b.final_score})` : ""}.
      </>
    );
  } else if (s.slam_finals > 0) {
    lines.push(
      `Reached ${s.slam_finals} Grand Slam final${s.slam_finals === 1 ? "" : "s"} without a title.`
    );
  }

  // Best surface — only if record there is notable.
  const best = s.surfaces.find((r) => r.surface === s.best_surface);
  if (best && best.wins + best.losses >= 10) {
    const surfacePct = Math.round((best.wins / (best.wins + best.losses)) * 100);
    if (surfacePct > winPct + 3) {
      lines.push(
        `Strongest on ${best.surface} (${best.wins}–${best.losses}, ${surfacePct}%).`,
      );
    }
  }

  // Recent form: last 20 matches.
  const recentTotal = s.recent_wins + s.recent_losses;
  if (recentTotal >= 10) {
    if (s.recent_losses === 0) {
      lines.push(
        `Currently on a ${s.recent_wins}-match winning streak in our records.`
      );
    } else if (s.recent_wins / recentTotal >= 0.85) {
      lines.push(
        `Last ${recentTotal} matches: ${s.recent_wins}–${s.recent_losses}.`
      );
    } else if (s.recent_losses / recentTotal >= 0.6) {
      lines.push(
        `Form has dipped — only ${s.recent_wins} wins in the last ${recentTotal} matches.`
      );
    } else {
      lines.push(
        `Last ${recentTotal} matches: ${s.recent_wins}–${s.recent_losses}.`
      );
    }
  }

  // Biggest rival.
  if (s.biggest_rival_slug && s.biggest_rival_name) {
    const total = s.biggest_rival_record_wins + s.biggest_rival_record_losses;
    let phrase: string;
    if (s.biggest_rival_record_wins > s.biggest_rival_record_losses) {
      phrase = `leads ${s.biggest_rival_record_wins}–${s.biggest_rival_record_losses}`;
    } else if (s.biggest_rival_record_losses > s.biggest_rival_record_wins) {
      phrase = `trails ${s.biggest_rival_record_wins}–${s.biggest_rival_record_losses}`;
    } else {
      phrase = `is tied ${s.biggest_rival_record_wins}–${s.biggest_rival_record_wins}`;
    }
    lines.push(
      <>
        Most-played opponent:{" "}
        <Link
          href={`/h2h/${s.slug}-vs-${s.biggest_rival_slug}`}
          className="text-accent underline decoration-dotted underline-offset-4 hover:text-accent-dim"
        >
          {s.biggest_rival_name}
        </Link>
        {" "}
        ({total} meeting{total === 1 ? "" : "s"}, {phrase}).
      </>
    );
  }

  return lines;
}
