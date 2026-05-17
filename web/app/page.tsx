import {
  api,
  mergeFeed,
  type MatchSummary,
  type NewsItemSummary,
  type TournamentsIndexResponse,
  type VideoItemSummary,
} from "@/lib/api";
import { AdSlot } from "@/components/AdSlot";
import { FeedList } from "@/components/FeedList";
import { HappeningNow } from "@/components/HappeningNow";
import { LiveStreamRefresh } from "@/components/LiveStreamRefresh";
import { SectionHeader } from "@/components/SectionHeader";
import { isLocalToday } from "@/lib/format";

export default async function HomePage() {
  const [live, upcomingFeatured, news, videos, tIndex] = await Promise.all([
    // Revalidate every 15s. Earlier this afternoon we tried 5s with
    // an SSE-triggered router.refresh() on top; the combination of
    // very frequent re-fetches across every page that mounts
    // LiveStreamRefresh tipped the backend into memory pressure and
    // it OOM'd. 15s is a reasonable cap on staleness for live tennis
    // and keeps the working set sane on the 2 GB box.
    api<MatchSummary[]>("/api/matches/live", { revalidate: 15 }).catch(() => []),
    api<MatchSummary[]>("/api/matches/upcoming-featured", { revalidate: 120 }).catch(() => []),
    api<NewsItemSummary[]>("/api/news?limit=8", { revalidate: 900 }).catch(() => []),
    api<VideoItemSummary[]>("/api/videos?limit=8", { revalidate: 900 }).catch(() => []),
    // 60s — the "live" section changes minute-to-minute as tournaments
    // start and singles finals complete. 10-minute caching caused Rome
    // to vanish from the live view minutes after it was correctly added
    // by the backend. Backend has its own 30s in-process cache so this
    // doesn't actually translate to 2× the backend traffic.
    api<TournamentsIndexResponse>("/api/tournaments/index", { revalidate: 60 }).catch(() => ({
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
      <LiveStreamRefresh enabled={todaysLive.some((m) => m.status === "live" || m.status === "suspended")} />

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
