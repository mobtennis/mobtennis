import {
  api,
  mergeFeed,
  type MatchSummary,
  type NewsItemSummary,
  type TournamentsIndexResponse,
  type VideoItemSummary,
} from "@/lib/api";
import { AdSlot } from "@/components/AdSlot";
import { DigestHomeCard } from "@/components/DigestHomeCard";
import { FeedList } from "@/components/FeedList";
import { HappeningNow } from "@/components/HappeningNow";
import { LiveStreamRefresh } from "@/components/LiveStreamRefresh";
import { SectionHeader } from "@/components/SectionHeader";
import { isLocalToday } from "@/lib/format";

// Disable Vercel's page-level ISR cache on the home page — it's the
// live tab, and first-load freshness matters during Slams. Without
// this, Vercel CDN serves stale HTML (`x-vercel-cache: STALE` /
// `age: N`) on the first hit of each ~30s window even though the
// fetches inside have `revalidate: 0`. The backend caches keep load
// bounded (5s in-process on /matches/live, 30s on /tournaments/index).
export const revalidate = 0;

export default async function HomePage() {
  const [live, upcomingFeatured, news, videos, tIndex] = await Promise.all([
    // Live-data fetches: revalidate: 0 ⇒ no Next.js fetch-cache.
    // Backend has its own 5-second in-process cache on /matches/live
    // and 30s on /tournaments/index, so concurrent visitors don't
    // multiply into N SQL queries — but every router.refresh() (from
    // SSE) actually sees fresh data, which is the whole point.
    api<MatchSummary[]>("/api/matches/live", { revalidate: 0 }).catch(() => []),
    api<MatchSummary[]>("/api/matches/upcoming-featured", { revalidate: 60 }).catch(() => []),
    api<NewsItemSummary[]>("/api/news?limit=8", { revalidate: 900 }).catch(() => []),
    api<VideoItemSummary[]>("/api/videos?limit=8", { revalidate: 900 }).catch(() => []),
    api<TournamentsIndexResponse>("/api/tournaments/index", { revalidate: 0 }).catch(() => ({
      sections: [] as TournamentsIndexResponse["sections"],
    })),
  ]);

  // /api/matches/live returns LIVE + SUSPENDED + FINISHED-in-last-36h.
  // Server can't know the client's timezone, so narrow finished
  // matches to "today in user's local time" here. Live/suspended
  // pass through unchanged.
  const todaysLive = live.filter(
    (m) =>
      m.status === "live" ||
      m.status === "suspended" ||
      (m.status === "finished" && isLocalToday(m.scheduled_at)),
  );

  // Merge news + videos into one chronological feed and cap.
  const feed = mergeFeed(news, videos).slice(0, 10);

  return (
    <div className="space-y-6">
      {/* SSE-driven refresh, always enabled. Earlier we gated on
          "has live matches AT PAGE LOAD" — that meant the listener
          died silently when the last match of the day ended, and
          new matches the next morning didn't reconnect without a
          full reload. SSE connection cost is one EventSource per
          tab; trivially cheap. */}
      <LiveStreamRefresh />

      {/* Weekly editorial digest — top of the page so the editorial
          voice is the first thing a visitor sees. Server-renders
          nothing if no digest exists yet, so a fresh deploy with an
          empty digests table still looks correct. */}
      <DigestHomeCard />

      <HappeningNow
        liveMatches={todaysLive}
        upcomingFeatured={upcomingFeatured}
        tIndex={tIndex}
      />

      <AdSlot slot="home-mid" />

      {/* Section always renders even when the feed is briefly empty.
          A transient fetch failure during a backend restart used to
          hide the whole block — with the FeedList empty-state and the
          helper's retry, worst case is a placeholder, not a missing
          section. */}
      <section>
        <SectionHeader title="News & highlights" actionHref="/news" />
        <div className="mt-2">
          <FeedList items={feed} />
        </div>
      </section>
    </div>
  );
}
