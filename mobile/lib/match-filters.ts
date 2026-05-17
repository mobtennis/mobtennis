/**
 * Match-type filter (mobile counterpart of web/lib/match-filters.ts).
 *
 * Persists the selected categories in SecureStore so the choice sticks
 * across launches and across both the Live tab and the Tournament-detail
 * screen. Module-level cache + listener set means the chip bar on every
 * screen stays in lockstep without prop-drilling.
 *
 * State model: a single global `filters` set + a `lockedScopes` set
 * tracking which scopes (all / atp / wta) the user has explicitly
 * emptied. The "fall back to all visible when intersection is empty"
 * rule is gated on whether the current scope is locked — that's what
 * makes "clear all" actually clear rather than re-firing the fallback.
 */

import * as SecureStore from "expo-secure-store";
import { useEffect, useMemo, useState } from "react";

import type { MatchSummary, Tour } from "@/lib/api";

export type MatchCategory =
  | "mens_singles"
  | "womens_singles"
  | "mens_doubles"
  | "womens_doubles"
  | "mixed_doubles";

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

const KEY = "mobtennis.match_filters";

type ClientState = {
  filters: Set<MatchCategory>;
  lockedScopes: Set<FilterScope>;
};

const _defaultState = (): ClientState => ({
  filters: new Set(ALL_CATEGORIES),
  lockedScopes: new Set(),
});

let _cached: ClientState = _defaultState();
let _hydrated = false;
const _listeners = new Set<(s: ClientState) => void>();

function isCategory(x: unknown): x is MatchCategory {
  return typeof x === "string" && (ALL_CATEGORIES as string[]).includes(x);
}

function isScope(x: unknown): x is FilterScope {
  return x === "all" || x === "atp" || x === "wta";
}

async function _hydrate(): Promise<void> {
  if (_hydrated) return;
  try {
    const raw = await SecureStore.getItemAsync(KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        // Schema v1: bare array. Treat as filters, locked starts empty.
        _cached = {
          filters: new Set(parsed.filter(isCategory)),
          lockedScopes: new Set(),
        };
      } else if (parsed && parsed.v === 2) {
        _cached = {
          filters: new Set((parsed.filters ?? []).filter(isCategory)),
          lockedScopes: new Set((parsed.locked ?? []).filter(isScope)),
        };
      }
    }
  } catch {
    // SecureStore unavailable in some test contexts — fall back to default.
  }
  _hydrated = true;
}

async function _persist(state: ClientState): Promise<void> {
  _cached = {
    filters: new Set(state.filters),
    lockedScopes: new Set(state.lockedScopes),
  };
  _hydrated = true;
  for (const fn of _listeners) fn(_cached);
  try {
    await SecureStore.setItemAsync(
      KEY,
      JSON.stringify({
        v: 2,
        filters: [..._cached.filters],
        locked: [..._cached.lockedScopes],
      }),
    );
  } catch {
    /* best effort */
  }
}

export function matchCategory(m: MatchSummary): MatchCategory | null {
  if ((m.round ?? "").toLowerCase().includes("mixed")) return "mixed_doubles";
  if (m.tournament_tour === "atp") return m.is_doubles ? "mens_doubles" : "mens_singles";
  if (m.tournament_tour === "wta") return m.is_doubles ? "womens_doubles" : "womens_singles";
  return null;
}

export function passesFilter(m: MatchSummary, selected: Set<MatchCategory>): boolean {
  const cat = matchCategory(m);
  if (cat === null) return true;
  return selected.has(cat);
}

export function visibleCategoriesForTour(
  tour: Tour | null | undefined,
): MatchCategory[] {
  if (tour === "atp") return ["mens_singles", "mens_doubles", "mixed_doubles"];
  if (tour === "wta") return ["womens_singles", "womens_doubles", "mixed_doubles"];
  return [...ALL_CATEGORIES];
}

export function scopeForTour(tour: Tour | null | undefined): FilterScope {
  if (tour === "atp") return "atp";
  if (tour === "wta") return "wta";
  return "all";
}

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

type UseMatchFiltersOpts = {
  visible?: readonly MatchCategory[];
  scope?: FilterScope;
};

export function useMatchFilters(opts: UseMatchFiltersOpts = {}) {
  const visible = opts.visible ?? ALL_CATEGORIES;
  const scope: FilterScope = opts.scope ?? "all";

  const [state, setStateLocal] = useState<ClientState>(() => ({
    filters: new Set(_cached.filters),
    lockedScopes: new Set(_cached.lockedScopes),
  }));

  useEffect(() => {
    let cancelled = false;
    _hydrate().then(() => {
      if (!cancelled) {
        setStateLocal({
          filters: new Set(_cached.filters),
          lockedScopes: new Set(_cached.lockedScopes),
        });
      }
    });
    const fn = (next: ClientState) => {
      setStateLocal({
        filters: new Set(next.filters),
        lockedScopes: new Set(next.lockedScopes),
      });
    };
    _listeners.add(fn);
    return () => {
      cancelled = true;
      _listeners.delete(fn);
    };
  }, []);

  const { filters, lockedScopes } = state;

  const effective = useMemo(
    () => effectiveFilters(filters, visible, scope, lockedScopes),
    [filters, visible, scope, lockedScopes],
  );

  const apply = (next: ClientState) => {
    void _persist(next);
    setStateLocal({
      filters: new Set(next.filters),
      lockedScopes: new Set(next.lockedScopes),
    });
  };

  return {
    filters,
    effective,
    allVisibleOn: visible.every((c) => effective.has(c)),
    scopeLocked: lockedScopes.has(scope),
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
      apply({ filters: base, lockedScopes: nextLocked });
    },
    showAllVisible: () => {
      const nextLocked = new Set(lockedScopes);
      nextLocked.delete(scope);
      apply({
        filters: new Set([...filters, ...visible]),
        lockedScopes: nextLocked,
      });
    },
    clearVisible: () => {
      const next = new Set([...filters].filter((c) => !visible.includes(c)));
      const nextLocked = new Set(lockedScopes);
      nextLocked.add(scope);
      apply({ filters: next, lockedScopes: nextLocked });
    },
  };
}

export function filterMatches(
  matches: MatchSummary[],
  selected: Set<MatchCategory>,
): MatchSummary[] {
  return matches.filter((m) => passesFilter(m, selected));
}
