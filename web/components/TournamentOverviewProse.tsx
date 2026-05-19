import type { TournamentOverview, TournamentDetail } from "@/lib/api";

/**
 * Editorial paragraph for a tournament page. Wraps the records +
 * stats + last-edition data into prose. Renders nothing when there
 * isn't enough data to say anything substantive (e.g., brand-new
 * tournament with no history).
 *
 * All copy is templated — no LLM. The shape of the sentences was
 * chosen so they read as a narrative paragraph rather than a list:
 * we mention the most decorated player first, then the recency
 * record, then the last edition.
 */
export function TournamentOverviewProse({
  tournament,
  overview,
}: {
  tournament: TournamentDetail;
  overview: TournamentOverview | null;
}) {
  if (!overview) return null;
  const lines = sentences(tournament, overview);
  if (lines.length === 0) return null;

  return (
    <section className="rounded-lg border border-ink-700 bg-ink-900 p-4 shadow-card">
      <h2 className="text-[10px] font-bold uppercase tracking-wider text-text-muted">
        At a glance
      </h2>
      <p className="mt-2 text-sm leading-6 text-text-secondary">
        {lines.map((line, i) => (
          <span key={i}>{line} </span>
        ))}
      </p>
    </section>
  );
}

function sentences(t: TournamentDetail, o: TournamentOverview): string[] {
  const lines: string[] = [];
  const tour = t.tour ? t.tour.toUpperCase() : "";
  const category = formatCategory(t.category);
  const surface = (t.surface || "").toLowerCase();
  const indoorLabel = t.indoor ? "indoor " : "";
  const monthName = monthLabel(o.stats.typical_month);

  // Opening line: format + surface + tour + month.
  if (category || surface) {
    const parts: string[] = [];
    if (category) parts.push(category);
    if (surface) parts.push(`${indoorLabel}${surface}-court`);
    const where = parts.join(" ");
    if (monthName && tour) {
      lines.push(
        `The ${t.name} is a ${where} ${tour} event, typically held in ${monthName}.`,
      );
    } else if (tour) {
      lines.push(`The ${t.name} is a ${where} ${tour} event.`);
    } else {
      lines.push(`The ${t.name} is a ${where} event.`);
    }
  }

  // History sentence — first held + total editions. Anchors the page in
  // time so a reader knows whether this is a 70-year-old institution or
  // a recent rebrand.
  if (o.stats.first_held && o.stats.total_editions && o.stats.total_editions > 1) {
    lines.push(
      `First held in ${o.stats.first_held}, the tournament has been contested ${o.stats.total_editions} times.`,
    );
  } else if (o.stats.first_held) {
    lines.push(`The tournament dates back to ${o.stats.first_held}.`);
  }

  // City / country flavour when we have it on the brand-page payload.
  if (t.city && t.country_code) {
    lines.push(
      `The event is staged in ${t.city}, with the draw running through the week leading up to its Sunday final.`,
    );
  }

  // Draw size — gives an idea of scale (a 128-draw Slam vs. a 32-draw
  // 250 is a very different commitment for the players who attend).
  if (o.stats.draw_size && o.stats.draw_size >= 32) {
    lines.push(
      `The singles main draw carries ${o.stats.draw_size} players.`,
    );
  }

  // Prize money — only at a level that's noteworthy.
  if (o.stats.prize_money && o.stats.prize_money >= 1_000_000) {
    lines.push(
      `Recent editions have carried a prize pool of around ${formatPrizeMoney(o.stats.prize_money)}.`,
    );
  }

  // Most-titles record. The detail string ("3 titles") already carries
  // the count; we re-mention the player by name in prose rather than
  // expecting the reader to parse the card grid.
  const mostTitles = o.records.find((r) => r.title === "Most titles");
  if (mostTitles && mostTitles.value && mostTitles.detail) {
    lines.push(
      `${mostTitles.value} holds the record for most titles (${mostTitles.detail.toLowerCase()}).`,
    );
  }

  // Most appearances — a different kind of record from titles, gives
  // shape to "who shows up here a lot."
  const mostApps = o.records.find((r) => r.title === "Most appearances");
  if (mostApps && mostApps.value && mostApps.detail) {
    lines.push(
      `${mostApps.value} has appeared in the draw the most (${mostApps.detail.toLowerCase()}).`,
    );
  }

  // Any other notable record we got back (youngest champion, longest
  // match, etc.) — keep one beyond titles/appearances to give the
  // paragraph a finishing kicker without listing every record on file.
  const otherRecord = o.records.find(
    (r) =>
      r.title !== "Most titles" &&
      r.title !== "Most appearances" &&
      r.value &&
      r.detail,
  );
  if (otherRecord) {
    lines.push(
      `${otherRecord.title} on record: ${otherRecord.value} (${(otherRecord.detail || "").toLowerCase()}).`,
    );
  }

  // Defending champion / last edition — closer so the reader knows where
  // the title currently lives.
  if (o.last_edition) {
    const le = o.last_edition;
    if (le.runner_up) {
      lines.push(
        `The ${le.year} edition was won by ${le.champion.full_name}, defeating ${le.runner_up.full_name}${le.final_score ? ` ${le.final_score}` : ""}.`,
      );
    } else {
      lines.push(`The ${le.year} edition was won by ${le.champion.full_name}.`);
    }
  }

  return lines;
}

function formatPrizeMoney(amount: number): string {
  if (amount >= 1_000_000) {
    return `$${(amount / 1_000_000).toFixed(amount % 1_000_000 === 0 ? 0 : 1)}M`;
  }
  return `$${Math.round(amount).toLocaleString("en-US")}`;
}

function formatCategory(category: string | null): string {
  if (!category) return "";
  switch (category.toLowerCase()) {
    case "grand_slam":
      return "Grand Slam";
    case "atp_1000":
    case "wta_1000":
      return "1000-level";
    case "atp_500":
    case "wta_500":
      return "500-level";
    case "atp_250":
    case "wta_250":
      return "250-level";
    case "atp_finals":
      return "ATP Finals";
    case "wta_finals":
      return "WTA Finals";
    default:
      return "";
  }
}

function monthLabel(m: number | null): string {
  if (!m) return "";
  return [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
  ][m - 1] || "";
}

