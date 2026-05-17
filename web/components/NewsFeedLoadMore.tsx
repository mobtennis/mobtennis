"use client";

import { Fragment, useMemo, useState } from "react";

import {
  api,
  mergeFeed,
  type FeedItem,
  type NewsItemSummary,
  type VideoItemSummary,
} from "@/lib/api";
import { FeedList } from "@/components/FeedList";

/**
 * Client wrapper around FeedList that supports "load more" pagination.
 *
 * Each load-more click renders a NEW independent FeedList block below
 * the previous ones, separated by a subtle divider. The initial block
 * and every previously-loaded block never re-render — their items
 * stay exactly where the user was looking when they clicked.
 *
 * Earlier we tried merging old + new into one big FeedList. The
 * masonry's shortest-column packer is deterministic *for its input*,
 * but the input changed (more items), and column-height ties broke
 * differently after re-pack — items previously in column A ended up
 * in column B, content visually relocated, and the user's viewport
 * showed something entirely different at the same scrollY. Separate
 * batches sidestep that entirely.
 */
export function NewsFeedLoadMore({
  initialNews,
  initialVideos,
  pageSize = 25,
}: {
  initialNews: NewsItemSummary[];
  initialVideos: VideoItemSummary[];
  pageSize?: number;
}) {
  // Cursors track the oldest timestamp loaded so far per source.
  // News and videos have independent publishing cadences; using one
  // shared cursor would skip whichever source's tail is older.
  const [oldestNews, setOldestNews] = useState<string | null>(
    initialNews[initialNews.length - 1]?.published_at ?? null,
  );
  const [oldestVideo, setOldestVideo] = useState<string | null>(
    initialVideos[initialVideos.length - 1]?.published_at ?? null,
  );
  const [batches, setBatches] = useState<Array<{ key: string; items: FeedItem[] }>>([]);
  const [loading, setLoading] = useState(false);
  const [newsExhausted, setNewsExhausted] = useState(false);
  const [videosExhausted, setVideosExhausted] = useState(false);

  const initialItems = useMemo(
    () => mergeFeed(initialNews, initialVideos),
    [initialNews, initialVideos],
  );
  const exhausted = newsExhausted && videosExhausted;

  const loadMore = async () => {
    if (loading || exhausted) return;
    setLoading(true);
    try {
      const [moreNews, moreVideos] = await Promise.all([
        newsExhausted || !oldestNews
          ? Promise.resolve([] as NewsItemSummary[])
          : api<NewsItemSummary[]>(
              `/api/news?limit=${pageSize}&before=${encodeURIComponent(oldestNews)}`,
            ).catch(() => [] as NewsItemSummary[]),
        videosExhausted || !oldestVideo
          ? Promise.resolve([] as VideoItemSummary[])
          : api<VideoItemSummary[]>(
              `/api/videos?limit=${Math.max(5, Math.floor(pageSize / 2))}&before=${encodeURIComponent(oldestVideo)}`,
            ).catch(() => [] as VideoItemSummary[]),
      ]);

      if (moreNews.length === 0) setNewsExhausted(true);
      else setOldestNews(moreNews[moreNews.length - 1].published_at);
      if (moreVideos.length === 0) setVideosExhausted(true);
      else setOldestVideo(moreVideos[moreVideos.length - 1].published_at);

      if (moreNews.length > 0 || moreVideos.length > 0) {
        const items = mergeFeed(moreNews, moreVideos);
        const anchor = items[0];
        const key = anchor
          ? `batch-${anchor.kind}-${anchor.item.id}`
          : `batch-${Date.now()}`;
        setBatches((prev) => [...prev, { key, items }]);
      }
    } finally {
      setLoading(false);
    }
  };

  const hasContent = initialItems.length > 0 || batches.length > 0;

  return (
    <div className="space-y-3">
      <FeedList items={initialItems} />
      {batches.map((b) => (
        <Fragment key={b.key}>
          <div
            className="flex items-center gap-2 pt-1 text-[10px] uppercase tracking-[0.2em] text-text-muted/60"
            aria-hidden
          >
            <div className="h-px flex-1 bg-ink-700/40" />
            <span>more</span>
            <div className="h-px flex-1 bg-ink-700/40" />
          </div>
          <FeedList items={b.items} />
        </Fragment>
      ))}
      {!exhausted && (
        <div className="flex justify-center pt-2">
          <button
            type="button"
            onClick={loadMore}
            disabled={loading}
            className="rounded-full border border-ink-700 bg-ink-900 px-4 py-2 text-xs font-semibold text-text-primary transition hover:border-ink-600 hover:bg-ink-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? "Loading…" : "Load more"}
          </button>
        </div>
      )}
      {exhausted && hasContent && (
        <p className="pt-2 text-center text-[11px] italic text-text-muted">
          That&apos;s everything we have.
        </p>
      )}
    </div>
  );
}
