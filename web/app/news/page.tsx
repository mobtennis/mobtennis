import {
  api,
  type NewsItemSummary,
  type VideoItemSummary,
} from "@/lib/api";
import { AdSlot } from "@/components/AdSlot";
import { FeedList } from "@/components/FeedList";
import { NewsFeedLoadMore } from "@/components/NewsFeedLoadMore";
import { SectionHeader } from "@/components/SectionHeader";
import { mergeFeed } from "@/lib/api";

export const metadata = { title: "News" };

// Number of news items rendered server-side at the top. Anything beyond
// this lives inside the client-side load-more wrapper so we don't pay
// page weight upfront for what most visitors won't scroll to.
const INITIAL_NEWS = 50;
const INITIAL_VIDEOS = 20;
const ABOVE_FOLD = 5;

export default async function NewsPage() {
  // Fetch news + videos in parallel, merge by date so the page reads
  // like a single chronological feed mixing headlines and highlights.
  const [news, videos] = await Promise.all([
    api<NewsItemSummary[]>(`/api/news?limit=${INITIAL_NEWS}`, { revalidate: 900 }).catch(
      () => [] as NewsItemSummary[],
    ),
    api<VideoItemSummary[]>(`/api/videos?limit=${INITIAL_VIDEOS}`, { revalidate: 900 }).catch(
      () => [] as VideoItemSummary[],
    ),
  ]);

  // Split: a small above-the-fold block of the freshest items rendered
  // statically, then everything else inside the client-side load-more
  // wrapper. Splitting by *merged item count* (not per-source) keeps the
  // top of the page mixed news/highlights, like the rest of the feed.
  const merged = mergeFeed(news, videos);
  const above = merged.slice(0, ABOVE_FOLD);
  const aboveIds = new Set(above.map((e) => `${e.kind}:${e.item.id}`));
  const restNews = news.filter((n) => !aboveIds.has(`news:${n.id}`));
  const restVideos = videos.filter((v) => !aboveIds.has(`video:${v.id}`));

  return (
    <div className="space-y-3">
      <SectionHeader title="News" subtitle="Headlines and highlights from across the tennis world" />
      <FeedList items={above} />
      {(restNews.length > 0 || restVideos.length > 0) && <AdSlot slot="news-mid" />}
      {(restNews.length > 0 || restVideos.length > 0) && (
        <NewsFeedLoadMore initialNews={restNews} initialVideos={restVideos} />
      )}
    </div>
  );
}
