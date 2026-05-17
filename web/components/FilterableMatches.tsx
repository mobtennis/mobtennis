"use client";

import type { MatchSummary } from "@/lib/api";
import { SectionHeader } from "@/components/SectionHeader";
import { TournamentGroups } from "@/components/TournamentGroup";
import { type FilterScope, type MatchCategory } from "@/lib/match-filters";
import { useFilteredMatches } from "@/lib/match-filters-client";

/**
 * Match list with the match-type filter applied. If the filter zeroes
 * the list out, the whole section disappears so the user isn't left
 * looking at an empty section.
 *
 * The filter bar itself is rendered once per page (above all sections);
 * this component only does the filtering + display. Pages that
 * restrict the visible categories pass `visible` through so we filter
 * with the same effective set.
 *
 * The header does NOT include a match count — the per-tournament
 * cards inside already show "N match(es)" each, so a top-level count
 * would be a redundant second number on the same row.
 */
export function FilterableMatches({
  title,
  matches,
  showSurface = true,
  visible,
  scope,
}: {
  title: string;
  matches: MatchSummary[];
  showSurface?: boolean;
  visible?: readonly MatchCategory[];
  scope?: FilterScope;
}) {
  const filtered = useFilteredMatches(matches, { visible, scope });
  if (filtered.length === 0) return null;
  return (
    <section>
      <SectionHeader title={title} />
      <div className="mt-2">
        <TournamentGroups matches={filtered} showSurface={showSurface} />
      </div>
    </section>
  );
}
