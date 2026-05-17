/**
 * Match-type filter — pure helpers + types.
 *
 * No React imports here so this module is safe to import from both
 * server components (e.g. the tournament-detail page wants
 * `visibleCategoriesForTour`) and client components.
 *
 * The hooks (useMatchFilters, useFilteredMatches) live in
 * match-filters-client.ts which has `"use client"` and depends on this
 * module.
 *
 * Filter rules:
 *   - Each match has exactly one category, computed from
 *     `tournament_tour`, `is_doubles`, and whether the round label
 *     mentions "mixed".
 *   - Tournament-detail pages restrict the visible categories (an ATP
 *     page has no women's chips, a WTA page has no men's chips).
 *   - If the user's saved selection has no overlap with what's
 *     applicable in the current view, we fall back to "all visible"
 *     so the page doesn't render empty — UNLESS the user has
 *     explicitly cleared this scope, in which case "really empty"
 *     means really empty.
 */

import type { MatchSummary, Tour } from "@/lib/api";

export type MatchCategory =
  | "mens_singles"
  | "womens_singles"
  | "mens_doubles"
  | "womens_doubles"
  | "mixed_doubles";

/** Logical scope of a chip-bar instance. Maps onto the kind of page
 *  the user is on. Used to track which scopes have been explicitly
 *  emptied (locked) so the fallback rule honours the user's intent. */
export type FilterScope = "all" | "atp" | "wta";

export const ALL_CATEGORIES: MatchCategory[] = [
  "mens_singles",
  "womens_singles",
  "mens_doubles",
  "womens_doubles",
  "mixed_doubles",
];

export const CATEGORY_LABELS: Record<MatchCategory, string> = {
  mens_singles: "Men's singles",
  womens_singles: "Women's singles",
  mens_doubles: "Men's doubles",
  womens_doubles: "Women's doubles",
  mixed_doubles: "Mixed doubles",
};

export const STORAGE_KEY = "mobtennis:match_filters";
export const CHANGE_EVENT = "mobtennis:match_filters_changed";


/** Categories that make sense to surface in a tour-restricted view. */
export function visibleCategoriesForTour(
  tour: Tour | null | undefined,
): MatchCategory[] {
  if (tour === "atp") return ["mens_singles", "mens_doubles", "mixed_doubles"];
  if (tour === "wta") return ["womens_singles", "womens_doubles", "mixed_doubles"];
  return [...ALL_CATEGORIES];
}


/** Scope name corresponding to a tour. The "all" scope is for
 *  multi-tour views (home / live tab). */
export function scopeForTour(tour: Tour | null | undefined): FilterScope {
  if (tour === "atp") return "atp";
  if (tour === "wta") return "wta";
  return "all";
}


export function matchCategory(m: MatchSummary): MatchCategory | null {
  // Mixed doubles isn't its own flag in the API — detect via round label.
  // Always wins because mixed sometimes uses tour=atp arbitrarily.
  if ((m.round ?? "").toLowerCase().includes("mixed")) return "mixed_doubles";
  if (m.tournament_tour === "atp") return m.is_doubles ? "mens_doubles" : "mens_singles";
  if (m.tournament_tour === "wta") return m.is_doubles ? "womens_doubles" : "womens_singles";
  return null;
}


export function isCategory(x: unknown): x is MatchCategory {
  return typeof x === "string" && (ALL_CATEGORIES as string[]).includes(x);
}

export function isScope(x: unknown): x is FilterScope {
  return x === "all" || x === "atp" || x === "wta";
}


/**
 * Compute what to actually show given the user's saved selection, the
 * categories visible in this view, and which scopes the user has
 * explicitly cleared. The rules are:
 *
 *   - if intersection of filters ∩ visible is non-empty → return that
 *     (the obvious case)
 *   - if intersection is empty and this scope is in `lockedScopes` →
 *     return empty (the user explicitly cleared; honour it)
 *   - if intersection is empty and scope is NOT locked → fall back to
 *     visible (the user has a preference from another context that
 *     doesn't apply here; show everything so the page isn't empty)
 */
export function effectiveFilters(
  filters: Set<MatchCategory>,
  visible: readonly MatchCategory[],
  scope: FilterScope,
  lockedScopes: ReadonlySet<FilterScope>,
): Set<MatchCategory> {
  const visibleSet = new Set(visible);
  const inter = new Set<MatchCategory>();
  for (const c of filters) {
    if (visibleSet.has(c)) inter.add(c);
  }
  if (inter.size > 0) return inter;
  if (lockedScopes.has(scope)) return new Set();
  return visibleSet;
}


export function passesFilter(
  m: MatchSummary,
  selected: Set<MatchCategory>,
): boolean {
  const cat = matchCategory(m);
  // Matches whose tour or doubles flag is unknown bypass the filter so
  // they never silently disappear because of upstream data quirks.
  if (cat === null) return true;
  return selected.has(cat);
}
