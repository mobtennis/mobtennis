"use client";

/**
 * Client-only hooks for the match-type filter. Pure helpers + types
 * live in match-filters.ts so they can also be imported by server
 * components (the tournament-detail page needs `visibleCategoriesForTour`).
 *
 * State model: one global `filters` Set + a `lockedScopes` Set tracking
 * which scopes (all / atp / wta) the user has explicitly emptied. The
 * "fall back to all visible when intersection is empty" rule is gated
 * on whether the current scope is locked — that's what makes
 * "clear all" actually clear rather than re-firing the fallback.
 */

import { useEffect, useMemo, useState } from "react";

import type { MatchSummary } from "@/lib/api";
import {
  ALL_CATEGORIES,
  CHANGE_EVENT,
  type FilterScope,
  type MatchCategory,
  STORAGE_KEY,
  effectiveFilters,
  isCategory,
  isScope,
  passesFilter,
} from "@/lib/match-filters";


type PersistedV2 = {
  v: 2;
  filters: MatchCategory[];
  locked: FilterScope[];
};

type ClientState = {
  filters: Set<MatchCategory>;
  lockedScopes: Set<FilterScope>;
};

const DEFAULT_STATE = (): ClientState => ({
  filters: new Set(ALL_CATEGORIES),
  lockedScopes: new Set(),
});


function loadFromStorage(): ClientState {
  if (typeof window === "undefined") return DEFAULT_STATE();
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_STATE();
    const parsed = JSON.parse(raw);
    // Schema v1 was a bare array of MatchCategory. Treat any old data
    // as the filters set; locked starts empty so existing users don't
    // suddenly see different behaviour on first load.
    if (Array.isArray(parsed)) {
      return {
        filters: new Set(parsed.filter(isCategory)),
        lockedScopes: new Set(),
      };
    }
    if (parsed && parsed.v === 2) {
      const v2 = parsed as PersistedV2;
      return {
        filters: new Set((v2.filters ?? []).filter(isCategory)),
        lockedScopes: new Set((v2.locked ?? []).filter(isScope)),
      };
    }
    return DEFAULT_STATE();
  } catch {
    return DEFAULT_STATE();
  }
}

function saveToStorage(state: ClientState): void {
  if (typeof window === "undefined") return;
  const payload: PersistedV2 = {
    v: 2,
    filters: [...state.filters],
    locked: [...state.lockedScopes],
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  window.dispatchEvent(new CustomEvent(CHANGE_EVENT));
}


type UseMatchFiltersOpts = {
  visible?: readonly MatchCategory[];
  scope?: FilterScope;
};

export function useMatchFilters(opts: UseMatchFiltersOpts = {}) {
  const visible = opts.visible ?? ALL_CATEGORIES;
  const scope: FilterScope = opts.scope ?? "all";

  const [state, setState] = useState<ClientState>(() => DEFAULT_STATE());

  useEffect(() => {
    setState(loadFromStorage());
    const handler = () => setState(loadFromStorage());
    window.addEventListener(CHANGE_EVENT, handler);
    window.addEventListener("storage", handler);
    return () => {
      window.removeEventListener(CHANGE_EVENT, handler);
      window.removeEventListener("storage", handler);
    };
  }, []);

  const { filters, lockedScopes } = state;

  const effective = useMemo(
    () => effectiveFilters(filters, visible, scope, lockedScopes),
    [filters, visible, scope, lockedScopes],
  );

  const persist = (next: ClientState) => {
    saveToStorage(next);
    setState(next);
  };

  return {
    filters,
    effective,
    /** True if every category in `visible` is currently shown. */
    allVisibleOn: visible.every((c) => effective.has(c)),
    /** True if the current scope is locked (user explicitly cleared). */
    scopeLocked: lockedScopes.has(scope),
    /**
     * Toggle one category. Two side effects:
     *   1. If the view is in the "fallback" state (saved selection has
     *      no overlap here and we're NOT locked), concretise to
     *      filters ∪ visible first so the resulting toggle reads as
     *      "user has these specific categories on" rather than
     *      re-triggering the fallback rule.
     *   2. Any toggle action unlocks the scope (the user is
     *      expressing a positive preference, not "show nothing").
     */
    toggle: (c: MatchCategory) => {
      const inter = [...filters].some((x) => visible.includes(x));
      const inFallback = !inter && !lockedScopes.has(scope);
      const base = inFallback
        ? new Set<MatchCategory>([...filters, ...visible])
        : new Set(filters);
      if (base.has(c)) base.delete(c);
      else base.add(c);
      const nextLocked = new Set(lockedScopes);
      nextLocked.delete(scope);
      persist({ filters: base, lockedScopes: nextLocked });
    },
    /** Make every visible chip on (also unlocks the scope). */
    showAllVisible: () => {
      const nextLocked = new Set(lockedScopes);
      nextLocked.delete(scope);
      persist({
        filters: new Set([...filters, ...visible]),
        lockedScopes: nextLocked,
      });
    },
    /** Remove every visible chip from saved selection AND lock the
     *  scope so the fallback rule doesn't re-show everything. */
    clearVisible: () => {
      const next = new Set([...filters].filter((c) => !visible.includes(c)));
      const nextLocked = new Set(lockedScopes);
      nextLocked.add(scope);
      persist({ filters: next, lockedScopes: nextLocked });
    },
  };
}


export function useFilteredMatches(
  matches: MatchSummary[],
  opts: UseMatchFiltersOpts = {},
): MatchSummary[] {
  const { effective } = useMatchFilters(opts);
  return useMemo(
    () => matches.filter((m) => passesFilter(m, effective)),
    [matches, effective],
  );
}
