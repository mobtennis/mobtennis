import Link from "next/link";
import { notFound } from "next/navigation";

import {
  api,
  mergeFeed,
  type MatchSummary,
  type NewsItemSummary,
  type PlayerDetail,
  type PlayerImage as PlayerImageRef,
  type PlayerSnapshot,
  type TournamentHistoryEntry,
  type VideoItemSummary,
} from "@/lib/api";
import { AdSlot } from "@/components/AdSlot";
import { AutoRefresh } from "@/components/AutoRefresh";
import { ExternalLinks } from "@/components/ExternalLinks";
import { FeedList } from "@/components/FeedList";
import { GetTheAppCard } from "@/components/GetTheAppCard";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PlayerPhotoStrip } from "@/components/PlayerPhotoStrip";
import { PlayerSnapshot as PlayerSnapshotProse } from "@/components/PlayerSnapshot";
import { SocialCard } from "@/components/SocialCard";
import { TournamentHistoryList } from "@/components/TournamentHistoryList";
import { TournamentGroups } from "@/components/TournamentGroup";
import { SectionHeader } from "@/components/SectionHeader";
import { TrackOnMount } from "@/components/TrackOnMount";
import { EVENTS } from "@/lib/analytics";
import { commonsImgVariant, flagEmoji } from "@/lib/format";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const player = await api<PlayerDetail>(`/api/players/${slug}`, {
    revalidate: 3600,
  }).catch(() => null);
  if (!player) return { title: slug.replace(/-/g, " ") };

  // Thin-page noindex: nobodys with neither a current nor career-high
  // ranking are usually wildcard / junior / qualifier rows whose page
  // has a name and not much else. Indexing them dilutes the site's
  // editorial signal without giving readers anything useful.
  const isThin = player.current_rank === null && player.career_high_rank === null;
  // Annotate the title with the player's current rank when known —
  // "Jannik Sinner — ATP #1" reads better than a bare name in browser
  // tabs and search snippets. Falls back to bare name for retired or
  // unranked players.
  const rankSuffix = player.current_rank
    ? ` — ${(player.tour ?? "").toUpperCase()} #${player.current_rank}`.replace(/  +/g, " ")
    : "";
  return {
    title: `${player.full_name}${rankSuffix}`,
    ...(isThin ? { robots: { index: false, follow: true } } : {}),
  };
}

export default async function PlayerPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const player = await api<PlayerDetail>(`/api/players/${slug}`).catch(() => null);
  if (!player) notFound();

  const [matches, news, videos, history, snapshot, images] = await Promise.all([
    // 15s revalidate. SSE refresh ticks against this cache — anything
    // tighter and the backend gets pounded by routine revalidations.
    api<MatchSummary[]>(`/api/players/${slug}/matches?limit=20`, { revalidate: 15 }).catch(() => []),
    api<NewsItemSummary[]>(`/api/news?player_slug=${slug}&limit=10`).catch(() => []),
    api<VideoItemSummary[]>(`/api/videos?player_slug=${slug}&limit=10`).catch(() => []),
    api<TournamentHistoryEntry[]>(`/api/players/${slug}/tournament-history?limit=5`).catch(() => []),
    // Career snapshot changes only when finished matches land, but data
    // corrections (mislabeled qualifying matches, ingestion fixes) need
    // to propagate without a full ISR window. 10 min is a sensible
    // middle ground — cheap enough that the DB scan isn't a load
    // concern, fresh enough that wrong claims don't stick for an hour
    // after a fix ships.
    api<PlayerSnapshot>(`/api/players/${slug}/snapshot`, { revalidate: 600 }).catch(() => null),
    // Photo collection. Cached aggressively — Wikipedia editors add
    // new images on a per-tournament cadence, so an hourly window
    // catches them well within the freshness budget.
    api<PlayerImageRef[]>(`/api/players/${slug}/images`, { revalidate: 3600 }).catch(
      () => [] as PlayerImageRef[],
    ),
  ]);
  const feed = mergeFeed(news, videos);

  const live = matches.filter((m) => m.status === "live" || m.status === "suspended");
  const upcoming = matches.filter((m) => m.status === "scheduled");
  const recent = matches.filter((m) => m.status === "finished").slice(0, 10);

  return (
    <div className="space-y-6">
      <AutoRefresh enabled={live.some((m) => m.status === "live" || m.status === "suspended")} intervalMs={15_000} />
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

      <PlayerPhotoStrip images={images} fullName={player.full_name} />


      <dl className="grid grid-cols-2 gap-2 text-sm md:grid-cols-4">
        {player.birth_date && <Stat label="Born" value={new Date(player.birth_date).toLocaleDateString()} />}
        {player.height_cm && <Stat label="Height" value={`${player.height_cm} cm`} />}
        {player.plays && <Stat label="Plays" value={player.plays} />}
        {player.turned_pro && <Stat label="Turned pro" value={player.turned_pro.toString()} />}
      </dl>

      <PlayerSnapshotProse snapshot={snapshot} />

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
        {/* Sends to search with the first player pre-selected. Previously
            linked to `/h2h/${slug}-vs-` which crawlers latched onto and
            hammered, helping take the box down with an empty-slug query
            pileup. Routing through search makes the user pick a real
            second player before the H2H endpoint is even hit. */}
        <Link
          href={`/search?h2h=${slug}`}
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
          {/* bg-top instead of bg-center: portrait-shaped infobox
              photos crop to chest/torso under bg-center, which got
              awkward fast. Top-anchoring keeps the face in the
              visible band. Proper fix below picks a landscape hero
              when one exists. Commons thumb at 1280 — wide enough
              for desktop 1024+ viewports, slim enough to not waste
              ~5MB of full-res for a 176px-tall band. */}
          <div
            className="h-44 bg-cover bg-top"
            style={{
              backgroundImage: `url(${commonsImgVariant(player.hero_image_url ?? player.image_url, 1280)})`,
            }}
            aria-hidden
          />
          <div className="absolute inset-0 bg-gradient-to-t from-ink-900 via-ink-900/60 to-transparent" />
          <div className="relative -mt-12 flex items-end gap-4 p-4">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={commonsImgVariant(player.image_url, 192) ?? player.image_url ?? ""}
              alt={player.full_name}
              className="h-20 w-20 shrink-0 rounded-full border-2 border-ink-900 object-cover shadow-lg"
            />
            <PlayerHeading player={player} />
          </div>
          {/* Photo credit — required by CC-BY family licenses. Only
              renders when the image came from a source that demands
              attribution (Wikipedia/Commons); api-tennis thumbs and
              manual uploads stay credit-less. */}
          {player.image_source === "wikipedia" && player.image_credit && (
            <PlayerPhotoCredit
              credit={player.image_credit}
              licenseUrl={player.image_license_url}
            />
          )}
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


function PlayerPhotoCredit({
  credit,
  licenseUrl,
}: {
  credit: string;
  licenseUrl: string | null;
}) {
  // Split on the " · " the backend inserted between artist and
  // license short-name so we can link only the license portion.
  const parts = credit.split(" · ");
  const artist = parts.length > 1 ? parts[0] : credit;
  const license = parts.length > 1 ? parts[1] : null;
  return (
    <div className="relative px-4 pb-3 pt-1 text-[11px] text-text-muted">
      Photo: {artist}
      {license && (
        <>
          {" · "}
          {licenseUrl ? (
            <a
              href={licenseUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="underline decoration-dotted underline-offset-2 hover:text-text-secondary"
            >
              {license}
            </a>
          ) : (
            license
          )}
        </>
      )}
    </div>
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


