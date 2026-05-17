"use client";

import clsx from "clsx";

import { EVENTS } from "@/lib/analytics";
import { analytics } from "@/lib/analytics-client";
import {
  ALL_CATEGORIES,
  CATEGORY_LABELS,
  type FilterScope,
  type MatchCategory,
} from "@/lib/match-filters";
import { useMatchFilters } from "@/lib/match-filters-client";

type Props = {
  /** Categories to surface in this view. Defaults to all five. Tournament
   *  detail pages narrow this to the relevant tour. */
  visible?: readonly MatchCategory[];
  /** Logical scope used to track per-context lock state (so "clear all"
   *  on the ATP page only locks the ATP scope, not WTA / Live). */
  scope?: FilterScope;
};

export function MatchFilterBar({ visible = ALL_CATEGORIES, scope }: Props) {
  const { effective, toggle, allVisibleOn, showAllVisible, clearVisible } =
    useMatchFilters({ visible, scope });

  return (
    <div className="flex items-center gap-2 overflow-x-auto py-1 no-scrollbar">
      {visible.map((cat) => {
        const on = effective.has(cat);
        return (
          <button
            key={cat}
            type="button"
            onClick={() => {
              analytics.track(EVENTS.filterToggled, {
                category: cat,
                action: on ? "off" : "on",
                scope: scope ?? "all",
              });
              toggle(cat);
            }}
            aria-pressed={on}
            className={clsx(
              "shrink-0 rounded-full border px-3 py-1 text-xs font-medium transition",
              on
                ? "border-accent bg-accent/10 text-accent"
                : "border-ink-700 bg-ink-900 text-text-muted hover:text-text-secondary",
            )}
          >
            {CATEGORY_LABELS[cat]}
          </button>
        );
      })}
      <button
        type="button"
        onClick={allVisibleOn ? clearVisible : showAllVisible}
        className="shrink-0 text-[11px] text-text-muted underline decoration-dotted underline-offset-4 hover:text-text-primary"
      >
        {allVisibleOn ? "clear all" : "show all"}
      </button>
    </div>
  );
}
