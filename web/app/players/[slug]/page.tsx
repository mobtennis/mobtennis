import Link from "next/link";
import { notFound } from "next/navigation";

import {
  api,
  mergeFeed,
  type MatchSummary,
  type NewsItemSummary,
  type PlayerDetail,
  type TournamentHistoryEntry,
  type VideoItemSummary,
} from "@/lib/api";
import { AdSlot } from "@/components/AdSlot";
import { LiveStreamRefresh } from "@/components/LiveStreamRefresh";
import { ExternalLinks } from "@/components/ExternalLinks";
import { FeedList } from "@/components/FeedList";
import { GetTheAppCard } from "@/components/GetTheAppCard";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { SocialCard } from "@/components/SocialCard";
import { TournamentHistoryList } from "@/components/TournamentHistoryList";
import { TournamentGroups } from "@/components/TournamentGroup";
import { SectionHeader } from "@/components/SectionHeader";
import { TrackOnMount } from "@/components/TrackOnMount";
import { EVENTS } from "@/lib/analytics";
import { flagEmoji } from "@/lib/format";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return { title: slug.replace(/-/g, " ") };
}

export default async function PlayerPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const player = await api<PlayerDetail>(`/api/players/${slug}`).catch(() => null);
  if (!player) notFound();

  const [matches, news, videos, history] = await Promise.all([
    // 15s revalidate. SSE refresh ticks against this cache — anything
    // tighter and the backend gets pounded by routine revalidations.
    api<MatchSummary[]>(`/api/players/${slug}/matches?limit=20`, { revalidate: 15 }).catch(() => []),
    api<NewsItemSummary[]>(`/api/news?player_slug=${slug}&limit=10`).catch(() => []),
    api<VideoItemSummary[]>(`/api/videos?player_slug=${slug}&limit=10`).catch(() => []),
    api<TournamentHistoryEntry[]>(`/api/players/${slug}/tournament-history?limit=5`).catch(() => []),
  ]);
  const feed = mergeFeed(news, videos);

  const live = matches.filter((m) => m.status === "live" || m.status === "suspended");
  const upcoming = matches.filter((m) => m.status === "scheduled");
  const recent = matches.filter((m) => m.status === "finished").slice(0, 10);

  return (
    <div className="space-y-6">
      <LiveStreamRefresh enabled={live.some((m) => m.status === "live" || m.status === "suspended")} />
      <TrackOnMount
        event={EVENTS.playerOpened}
        properties={{ slug: player.slug, tour: player.tour }}
      />

      <PlayerHero player={player} />

      <GetTheAppCard action={`follow ${player.full_name}`} />

      {player.bio && (
        <section className="rounded-lg border border-ink-700 bg-ink-900 p-4 shadow-card">
          <p className="text-sm leading-relaxed text-text-secondary">{player.bio}</p>
          {player.wikipedia_url && (
            <a
              href={player.wikipedia_url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 inline-block text-xs font-medium text-accent hover:text-accent-dim"
            >
              Read more on Wikipedia →
            </a>
          )}
        </section>
      )}

      <dl className="grid grid-cols-2 gap-2 text-sm md:grid-cols-4">
        {player.birth_date && <Stat label="Born" value={new Date(player.birth_date).toLocaleDateString()} />}
        {player.height_cm && <Stat label="Height" value={`${player.height_cm} cm`} />}
        {player.plays && <Stat label="Plays" value={player.plays} />}
        {player.turned_pro && <Stat label="Turned pro" value={player.turned_pro.toString()} />}
      </dl>

      <AdSlot slot="player-mid" />

      {live.length > 0 && (
        <section>
          <SectionHeader title="Live" />
          <div className="mt-2"><TournamentGroups matches={live} /></div>
        </section>
      )}

      {upcoming.length > 0 && (
        <section>
          <SectionHeader title="Upcoming" />
          <div className="mt-2"><TournamentGroups matches={upcoming} /></div>
        </section>
      )}

      {recent.length > 0 && (
        <section>
          <SectionHeader title="Recent results" />
          <div className="mt-2"><TournamentGroups matches={recent} /></div>
        </section>
      )}

      {history.length > 0 && (
        <section>
          <SectionHeader title="Tournament history" subtitle="How far they got, most recent first" />
          <div className="mt-2">
            <TournamentHistoryList
              playerSlug={slug}
              initial={history}
              initialOffset={history.length}
            />
          </div>
        </section>
      )}

      {feed.length > 0 && (
        <section>
          <SectionHeader title="News & highlights" />
          <div className="mt-2"><FeedList items={feed} /></div>
        </section>
      )}

      <SocialCard
        instagramHandle={player.instagram_handle}
        twitterHandle={player.twitter_handle}
        latestPostUrl={player.instagram_latest_post_url}
        playerName={player.full_name}
      />

      <ExternalLinks name={player.full_name} tour={player.tour} />

      <div className="text-center">
        <Link
          href={`/h2h/${slug}-vs-`}
          className="inline-block rounded-full border border-ink-700 bg-ink-900 px-4 py-2 text-xs font-medium hover:border-ink-600"
        >
          Compare head-to-head →
        </Link>
      </div>
    </div>
  );
}

function PlayerHero({ player }: { player: PlayerDetail }) {
  const hasPhoto = Boolean(player.image_url);
  return (
    <header className="relative overflow-hidden rounded-lg border border-ink-700 bg-ink-900 shadow-card">
      {hasPhoto ? (
        <>
          <div
            className="h-44 bg-cover bg-center"
            style={{ backgroundImage: `url(${player.image_url})` }}
            aria-hidden
          />
          <div className="absolute inset-0 bg-gradient-to-t from-ink-900 via-ink-900/60 to-transparent" />
          <div className="relative -mt-12 flex items-end gap-4 p-4">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={player.image_url ?? ""}
              alt={player.full_name}
              className="h-20 w-20 shrink-0 rounded-full border-2 border-ink-900 object-cover shadow-lg"
            />
            <PlayerHeading player={player} />
          </div>
        </>
      ) : (
        <div className="flex items-center gap-4 p-4">
          <PlayerAvatar
            name={player.full_name}
            imageUrl={null}
            countryCode={player.country_code}
            size="md"
          />
          <PlayerHeading player={player} />
        </div>
      )}
    </header>
  );
}

function PlayerHeading({ player }: { player: PlayerDetail }) {
  return (
    <div className="min-w-0 flex-1">
      <div className="flex items-center gap-2">
        <h1 className="truncate text-xl font-bold tracking-tight">{player.full_name}</h1>
        <span className="text-sm">{flagEmoji(player.country_code)}</span>
      </div>
      <div className="mt-1 flex items-center gap-3 text-xs text-text-secondary">
        <span className="rounded-full bg-ink-700/80 px-2 py-0.5 font-bold uppercase tracking-wider text-text-primary backdrop-blur">
          {player.tour.toUpperCase()}
        </span>
        {player.current_rank && (
          <span>
            <span className="text-text-muted">Rank</span> <span className="font-semibold tnum text-text-primary">#{player.current_rank}</span>
          </span>
        )}
        {player.career_high_rank && (
          <span>
            <span className="text-text-muted">High</span> <span className="font-semibold tnum">#{player.career_high_rank}</span>
          </span>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-ink-700 bg-ink-900 px-3 py-2">
      <dt className="text-[10px] font-bold uppercase tracking-wider text-text-muted">{label}</dt>
      <dd className="mt-0.5 text-sm font-medium">{value}</dd>
    </div>
  );
}
