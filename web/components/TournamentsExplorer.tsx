"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";

import { api, type IndexSection, type TournamentsIndexResponse } from "@/lib/api";
import { TournamentCard } from "@/components/TournamentCard";

const ALL = "__all__";
const PAGE_SIZE = 30;

export function TournamentsExplorer({ data }: { data: TournamentsIndexResponse }) {
  const [active, setActive] = useState<string>(ALL);

  const chips = useMemo(
    () => [{ key: ALL, title: "All" }, ...data.sections.map((s) => ({ key: s.key, title: s.title }))],
    [data.sections],
  );

  return (
    <div className="space-y-5">
      <nav
        aria-label="Filter by tier"
        className="-mx-3 sticky top-12 z-20 flex gap-2 overflow-x-auto bg-ink-950/95 px-3 py-2 backdrop-blur no-scrollbar"
      >
        {chips.map((c) => {
          const isActive = c.key === active;
          return (
            <button
              key={c.key}
              type="button"
              onClick={() => setActive(c.key)}
              className={clsx(
                "shrink-0 rounded-full border px-3 py-1.5 text-xs font-medium transition",
                isActive
                  ? "border-accent bg-accent/15 text-accent"
                  : "border-ink-700 bg-ink-900 text-text-secondary hover:border-ink-600 hover:text-text-primary",
              )}
              aria-pressed={isActive}
            >
              {c.title}
            </button>
          );
        })}
      </nav>

      {active === ALL ? (
        <AllSectionsView sections={data.sections} onPickSection={setActive} />
      ) : (
        <SingleSectionView
          // We seed the first page from the SSR payload so the user sees
          // content instantly. Subsequent pages are fetched client-side.
          sectionKey={active}
          initial={data.sections.find((s) => s.key === active) ?? null}
          onClear={() => setActive(ALL)}
        />
      )}
    </div>
  );
}

function AllSectionsView({
  sections,
  onPickSection,
}: {
  sections: IndexSection[];
  onPickSection: (k: string) => void;
}) {
  return (
    <>
      {sections.map((section) => (
        <section key={section.key}>
          <header className="flex items-baseline justify-between px-1">
            <h2 className="text-base font-semibold tracking-tight">{section.title}</h2>
            <span className="text-[11px] text-text-muted">
              {section.total} {section.total === 1 ? "event" : "events"}
            </span>
          </header>
          <ul className="mt-2 space-y-2">
            {section.tournaments.map((t) => (
              <li key={`${t.slug}-${t.year}-${t.tour}`}>
                <TournamentCard t={t} />
              </li>
            ))}
          </ul>
          {section.total > section.tournaments.length && (
            <div className="mt-2 px-1">
              <button
                type="button"
                onClick={() => onPickSection(section.key)}
                className="text-xs font-semibold text-accent hover:text-accent-dim"
              >
                View all {section.total} →
              </button>
            </div>
          )}
        </section>
      ))}
    </>
  );
}

function SingleSectionView({
  sectionKey,
  initial,
  onClear,
}: {
  sectionKey: string;
  initial: IndexSection | null;
  onClear: () => void;
}) {
  // We accumulate pages locally. SSR-seeded first page is page 0; subsequent
  // pages come from /api/tournaments/sections/{key} via the api helper.
  const [pages, setPages] = useState<IndexSection[]>(initial ? [initial] : []);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  // Reset when the active section changes.
  useEffect(() => {
    setPages(initial ? [initial] : []);
    setError(null);
  }, [sectionKey, initial]);

  const items = useMemo(() => pages.flatMap((p) => p.tournaments), [pages]);
  const total = pages[0]?.total ?? 0;
  const title = pages[0]?.title ?? "";
  const hasMore = items.length < total;

  // IntersectionObserver-driven infinite scroll. Falls back gracefully if
  // unsupported — the user just won't auto-load (manual "Load more" still
  // works via the button below).
  useEffect(() => {
    if (!hasMore || loading) return;
    const node = sentinelRef.current;
    if (!node || typeof IntersectionObserver === "undefined") return;
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) loadMore();
      },
      { rootMargin: "300px 0px" },
    );
    obs.observe(node);
    return () => obs.disconnect();
    // loadMore is stable enough for our purposes; depending on `items.length`
    // re-attaches the observer after each page so the next sentinel triggers.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasMore, loading, items.length]);

  const loadMore = async () => {
    if (loading || !hasMore) return;
    setLoading(true);
    setError(null);
    try {
      const next = await api<IndexSection>(
        `/api/tournaments/sections/${sectionKey}?offset=${items.length}&limit=${PAGE_SIZE}`,
      );
      setPages((prev) => [...prev, next]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load more.");
    } finally {
      setLoading(false);
    }
  };

  if (!initial) {
    return (
      <div className="rounded-lg border border-dashed border-ink-700 px-4 py-12 text-center text-sm text-text-muted">
        Nothing in this tier right now.
      </div>
    );
  }

  return (
    <section>
      <header className="flex items-baseline justify-between px-1">
        <h2 className="text-base font-semibold tracking-tight">{title}</h2>
        <button
          type="button"
          onClick={onClear}
          className="text-xs text-text-muted underline decoration-dotted underline-offset-4 hover:text-text-primary"
        >
          Show all tiers
        </button>
      </header>
      <p className="mt-1 px-1 text-xs text-text-muted">
        {items.length} of {total} {total === 1 ? "tournament" : "tournaments"}
      </p>

      <ul className="mt-3 space-y-2">
        {items.map((t) => (
          <li key={`${t.slug}-${t.year}-${t.tour}`}>
            <TournamentCard t={t} />
          </li>
        ))}
      </ul>

      <div ref={sentinelRef} aria-hidden className="h-1" />

      {hasMore && (
        <div className="mt-4 flex justify-center">
          <button
            type="button"
            onClick={loadMore}
            disabled={loading}
            className="rounded-md border border-ink-700 bg-ink-900 px-4 py-2 text-xs font-semibold text-text-primary hover:border-ink-600 disabled:opacity-50"
          >
            {loading ? "Loading…" : "Load more"}
          </button>
        </div>
      )}
      {error && (
        <p className="mt-2 text-center text-xs text-red-400">{error}</p>
      )}
    </section>
  );
}
