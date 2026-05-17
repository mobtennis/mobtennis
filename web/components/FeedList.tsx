"use client";

import type { FeedItem, NewsItemSummary } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import { VideoCard } from "@/components/VideoCard";

/**
 * Unified news + video feed. Loosely-chronological masonry:
 *
 *   - "narrow" items (news cards + portrait/Shorts videos) flow into
 *     a 2-column grid. We DON'T round-robin — every item lands in the
 *     currently-shorter column, which packs cards tightly and absorbs
 *     the big gaps you get when a 9:16 portrait sits next to a 1-line
 *     headline. Order within a column stays time-sorted top→bottom;
 *     across columns it's "newest-fills-the-shorter-side," which
 *     reads close to chronological without leaving voids.
 *
 *   - landscape videos break out as full-width banners between chunks.
 *     16:9 at 1-column width looks puny next to a 9:16 portrait in the
 *     same column. Spanning the container makes the landscape's pixel
 *     area at least match a portrait's, and visually punctuates the
 *     chronological flow.
 *
 * Heights are estimated from card type + text length — no DOM measure
 * needed, so SSR + first paint are stable and there's no layout
 * thrash. The estimator's units are abstract; only relative heights
 * matter to the packing decision.
 */
const COLS = 2;

/** Rough relative height of a card. Units are arbitrary — only the
 * relative ordering matters for shortest-column packing. */
function estimateHeight(item: FeedItem): number {
  if (item.kind === "video") {
    const v = item.item;
    // Portrait 9:16 → tall; landscape shouldn't reach here (it's a wide
    // breakout above) but cover the case anyway.
    const videoH = v.is_portrait ? 178 : 56;
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
  if (items.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-ink-700 px-4 py-8 text-center text-text-muted">
        Nothing here yet.
      </div>
    );
  }

  type Group =
    | { kind: "chunk"; items: FeedItem[] }
    | { kind: "wide"; video: Extract<FeedItem, { kind: "video" }> };
  const groups: Group[] = [];
  let buf: FeedItem[] = [];
  for (const entry of items) {
    const isLandscape = entry.kind === "video" && !entry.item.is_portrait;
    if (isLandscape) {
      if (buf.length > 0) {
        groups.push({ kind: "chunk", items: buf });
        buf = [];
      }
      groups.push({ kind: "wide", video: entry });
    } else {
      buf.push(entry);
    }
  }
  if (buf.length > 0) groups.push({ kind: "chunk", items: buf });

  return (
    <div className="flex flex-col gap-3">
      {groups.map((g) => {
        if (g.kind === "wide") {
          return <VideoCard key={`wide-${g.video.item.id}`} video={g.video.item} />;
        }
        // Key each chunk by the id of its first item so load-more
        // doesn't cause React to unmount + remount existing chunks
        // (which would kill any playing video and lose scroll
        // anchoring). The first item's id is stable as long as no
        // newer item is prepended — and load-more only appends.
        const anchor = g.items[0];
        const key = anchor
          ? `chunk-${anchor.kind}-${anchor.item.id}`
          : "chunk-empty";
        return <Chunk key={key} items={g.items} />;
      })}
    </div>
  );
}

function Chunk({ items }: { items: FeedItem[] }) {
  // Pack into the shorter column, in order. Ties go left so the layout
  // stays stable across re-renders.
  const cols: { items: FeedItem[]; height: number }[] = Array.from(
    { length: COLS },
    () => ({ items: [], height: 0 }),
  );
  for (const entry of items) {
    let target = 0;
    for (let i = 1; i < COLS; i++) {
      if (cols[i].height < cols[target].height) target = i;
    }
    cols[target].items.push(entry);
    cols[target].height += estimateHeight(entry);
  }
  return (
    <div className="grid grid-cols-2 gap-3">
      {cols.map((col, idx) => (
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
