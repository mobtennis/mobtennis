"use client";

import { useEffect, useState } from "react";

import type { FeedItem, NewsItemSummary } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import { VideoCard } from "@/components/VideoCard";

/**
 * Unified news + video feed. Loosely-chronological masonry: every
 * item flows into a column grid; each card lands in the currently-
 * shorter column. Order within a column stays time-sorted top→bottom;
 * across columns it's "newest-fills-the-shorter-side," which reads
 * close to chronological without leaving voids.
 *
 * 2 cols on mobile / 3 cols on ≥640 px. Video and news cards are
 * the same width; column width itself controls the displayed size
 * of YouTube thumbnails, and at 3 cols on a 768 px container the
 * column is ~240 px wide which is close to the source thumbnail
 * resolution — no more upscale-grain.
 *
 * Heights are estimated from card type + text length — no DOM
 * measure needed, so SSR + first paint are stable.
 */
function useColumnCount(): number {
  // SSR / first paint = 2 cols (mobile default); the effect
  // upgrades to 3 on wider screens after hydration. Match the
  // Tailwind sm breakpoint (640 px) so the JS-driven count agrees
  // with whatever utility classes we use elsewhere.
  const [cols, setCols] = useState(2);
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 640px)");
    const sync = () => setCols(mq.matches ? 3 : 2);
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);
  return cols;
}

/** Rough relative height of a card. Units are arbitrary — only the
 * relative ordering matters for shortest-column packing. */
function estimateHeight(item: FeedItem): number {
  if (item.kind === "video") {
    // Video frame height at column width: portrait 9:16 is tall,
    // landscape 16:9 is squat. Numbers are relative.
    const videoH = item.item.is_portrait ? 200 : 60;
    return videoH + 50; // title + meta chrome
  }
  // News card. Approx 30 chars per line at narrow column width.
  const n = item.item;
  const imageH = n.image_url ? 56 : 0; // aspect-video image
  const titleLines = Math.max(1, Math.ceil(n.title.length / 30));
  const summaryLines = n.summary ? Math.ceil(n.summary.length / 30) : 0;
  return imageH + titleLines * 20 + summaryLines * 16 + 40; // + padding/meta
}

export function FeedList({ items }: { items: FeedItem[] }) {
  const colCount = useColumnCount();
  if (items.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-ink-700 px-4 py-8 text-center text-text-muted">
        Nothing here yet.
      </div>
    );
  }

  // Pack into the shorter column, in order. Ties go left so the
  // layout stays stable across re-renders.
  const buckets: { items: FeedItem[]; height: number }[] = Array.from(
    { length: colCount },
    () => ({ items: [], height: 0 }),
  );
  for (const entry of items) {
    let target = 0;
    for (let i = 1; i < colCount; i++) {
      if (buckets[i].height < buckets[target].height) target = i;
    }
    buckets[target].items.push(entry);
    buckets[target].height += estimateHeight(entry);
  }

  // Tailwind needs the column-count class names to be literal
  // strings in the source so the JIT picks them up.
  const gridClass = colCount === 3 ? "grid grid-cols-3 gap-3" : "grid grid-cols-2 gap-3";

  return (
    <div className={gridClass}>
      {buckets.map((col, idx) => (
        <div key={idx} className="flex flex-col gap-3">
          {col.items.map((entry) =>
            entry.kind === "video" ? (
              <VideoCard key={`video-${entry.item.id}`} video={entry.item} />
            ) : (
              <NewsCard key={`news-${entry.item.id}`} item={entry.item} />
            ),
          )}
        </div>
      ))}
    </div>
  );
}

function NewsCard({ item }: { item: NewsItemSummary }) {
  return (
    <a
      href={item.source_url}
      target="_blank"
      rel="noopener noreferrer"
      className="group flex flex-col overflow-hidden rounded-md border border-ink-700 bg-ink-900 shadow-card transition hover:border-ink-600 hover:bg-ink-800"
    >
      {item.image_url && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={item.image_url}
          alt=""
          loading="lazy"
          className="aspect-video w-full object-cover transition group-hover:brightness-95"
        />
      )}
      <div className="flex flex-1 flex-col gap-1 px-3 py-2">
        {/* Title + summary wrap freely — no line-clamp. Cards grow as
            tall as the text needs; column-flow masonry absorbs the
            variable heights. */}
        <h3 className="text-sm font-semibold leading-snug text-text-primary">
          {item.title}
        </h3>
        {item.summary && (
          <p className="text-xs leading-snug text-text-secondary">
            {item.summary}
          </p>
        )}
        <div className="mt-auto flex items-center gap-2 pt-1 text-[11px] text-text-muted">
          <span className="font-medium uppercase tracking-wider">{item.source}</span>
          <span>·</span>
          <time dateTime={item.published_at}>{formatRelative(item.published_at)}</time>
        </div>
      </div>
    </a>
  );
}
