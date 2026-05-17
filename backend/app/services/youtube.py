"""YouTube highlight-video ingestion.

Pulls each configured channel's RSS feed (the free, public per-channel
feed at /feeds/videos.xml?channel_id=…), parses out videos, dedupes
by `video_id`, and writes VideoItem rows. The tagging step matches
player and tournament slugs from the title so the same keyword index
that powers news filtering also powers video filtering.

Embedding policy: we surface videos via YouTube's standard iframe
embed, never re-hosting or downloading. That's the explicit
TOS-compliant path and keeps revenue + analytics with the channel.

A follow-up pass will fuzzy-match each video to a specific Match row
(highlight title typically contains both players' last names + the
tournament name, which is enough to resolve a singles main-draw match
with high precision). Until then `match_id` is NULL on every row.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from time import mktime

import feedparser
import httpx
from sqlmodel import Session, select

from app.models.match import Match, MatchStatus
from app.models.player import Player
from app.models.tournament import Tournament
from app.models.video import VideoItem

log = logging.getLogger(__name__)


# Curated official tennis channels. Channel IDs come from
# `https://www.youtube.com/@HANDLE` → canonical URL contains the
# `UC...` id. RSS feed lives at:
#     https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}
#
# Adding a new channel: open the @handle URL in a browser, view source,
# search for `canonical" href="https://www.youtube.com/channel/UC` and
# paste the id below.
CHANNELS: list[tuple[str, str]] = [
    ("atptour",        "UCY_5h5zaSwN7Or4kIJDYNXA"),
    ("wta",            "UCaBIVVpHjq6j3tSyxwTE-8Q"),
    ("tennistv",       "UCbcxFkd6B9xUU54InHv4Tig"),
    ("tennischannel",  "UCDitdIjOjS9Myza9I21IqzQ"),
    ("rolandgarros",   "UCF3K1Jf8hjFW8qliei8fQ3A"),
    ("wimbledon",      "UCNa8NxMgSm7m4Ii9d4QGk1Q"),
    ("ausopen",        "UCeTKJSW1NTAkf27nNmjWt5A"),
    ("usopen",         "UCXbboag48Qlr78zzz6SkzkQ"),
]


_FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={cid}"


def _parse_published(entry: dict) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return datetime.fromtimestamp(mktime(parsed))


_YT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _video_id(entry: dict) -> str | None:
    """Pull the 11-char YouTube video id out of a feedparser entry. Tries
    the explicit yt:videoId first, falls back to parsing the link/id."""
    vid = entry.get("yt_videoid") or entry.get("yt:videoid")
    if isinstance(vid, str) and _YT_ID_RE.match(vid):
        return vid
    eid = entry.get("id") or ""
    if isinstance(eid, str) and eid.startswith("yt:video:"):
        candidate = eid[len("yt:video:"):]
        if _YT_ID_RE.match(candidate):
            return candidate
    link = entry.get("link") or ""
    m = re.search(r"[?&]v=([A-Za-z0-9_-]{11})", link)
    if m:
        return m.group(1)
    return None


def _thumbnail(entry: dict, video_id: str | None) -> str | None:
    media = entry.get("media_thumbnail")
    if isinstance(media, list) and media and isinstance(media[0], dict):
        url = media[0].get("url")
        if url:
            return url
    # Predictable YouTube thumbnail URL — useful when the feed omits the
    # media:thumbnail (rare but happens).
    if video_id:
        return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    return None


def _probe_orientation(video_id: str) -> bool | None:
    """Decide portrait vs landscape for a YouTube video.

    YouTube serves a special thumbnail at `i.ytimg.com/vi/{id}/oardefault.jpg`
    (the "original aspect ratio default") ONLY for portrait videos —
    Shorts and vertical reels. Landscape videos return 404 on that
    path. So a HEAD request is a reliable, cheap orientation signal.
    No HTML parsing, no auth, no consent gating (the image CDN doesn't
    enforce GDPR redirects the way youtube.com does for EU IPs).
    Each probe is one tiny HTTP HEAD, vs the 1MB watch-page fetch
    that earlier approaches required.

    Returns True if portrait, False if landscape, None on network
    error. NULL gets retried on next sync; falls back to landscape
    rendering in the UI in the meantime.
    """
    url = f"https://i.ytimg.com/vi/{video_id}/oardefault.jpg"
    try:
        r = httpx.head(url, timeout=5.0, follow_redirects=True)
        if r.status_code == 200:
            return True
        if r.status_code == 404:
            return False
        # Anything else (rate limit, 5xx) — keep NULL and retry.
        return None
    except Exception as e:
        log.debug("orientation probe failed for %s: %s", video_id, e)
        return None


def backfill_orientation(session: Session, limit: int = 50) -> int:
    """Probe orientation for any VideoItem rows where is_portrait IS
    NULL. Capped per run so a flood of new rows doesn't block sync
    (the next sync picks up the remainder). Returns count updated."""
    rows = session.exec(
        select(VideoItem).where(VideoItem.is_portrait.is_(None)).limit(limit)
    ).all()
    updated = 0
    for v in rows:
        result = _probe_orientation(v.video_id)
        if result is None:
            continue
        v.is_portrait = result
        session.add(v)
        updated += 1
    if updated:
        session.commit()
        log.info("orientation backfill: probed %d row(s)", updated)
    return updated


def _attribute_to_match(session: Session, video: VideoItem) -> int | None:
    """Resolve a video to a specific Match row using its tagged
    player/tournament slugs + publish date.

    Tiered selection — strict, then loosen the tournament filter:
      Tier 1: video has 2+ tagged players AND 1+ tagged tournament.
              Find the singles Match between exactly those two players
              in that tournament, completed, scheduled within ±365 days
              of the video's publish_at. Wide window because (players,
              tournament) is unique within a year anyway — and channels
              regularly post "Full Match" replays of Grand Slam finals
              months later. Without this, AO archive replays in May
              would never link to their January source match.
      Tier 2: video has 2+ tagged players, no tournament hit. Find a
              completed singles Match between those two players in
              any tournament, within ±14 days. Tight window because
              the tournament isn't constraining — H2H pairs play
              multiple times a year and we'd otherwise mis-attribute
              to the wrong meeting.

    Both tiers require exactly one matching Match row to assign.
    Multiple matches or none → leave NULL (better empty than wrong).
    Skips compilation/recap videos by requiring exactly two players.

    Returns the resolved match_id, or None if no confident match.
    """
    slugs = [s for s in (video.player_slugs or "").split(",") if s]
    if len(slugs) != 2:
        return None

    # Player slugs → ids. Both must exist.
    p_rows = session.exec(
        select(Player.id, Player.slug).where(Player.slug.in_(slugs))
    ).all()
    if len(p_rows) != 2:
        return None
    player_ids = {pid for pid, _ in p_rows}

    publish = video.published_at
    if publish is None:
        return None

    def _find(window_days: int, tournament_slug: str | None) -> int | None:
        """Return a Match.id if exactly one singles match exists between
        the two players within `±window_days` of publish, optionally
        narrowed to a tournament slug. Otherwise None."""
        lo = publish - timedelta(days=window_days)
        hi = publish + timedelta(days=window_days)
        stmt = (
            select(Match.id)
            .where(Match.player1_id.in_(player_ids))
            .where(Match.player2_id.in_(player_ids))
            .where(Match.player1_id != Match.player2_id)
            .where(Match.is_doubles == False)  # noqa: E712 — SQLAlchemy expr
            .where(Match.status == MatchStatus.FINISHED)
            .where(Match.scheduled_at.is_not(None))
            .where(Match.scheduled_at >= lo)
            .where(Match.scheduled_at <= hi)
        )
        if tournament_slug:
            stmt = stmt.join(
                Tournament, Tournament.id == Match.tournament_id
            ).where(Tournament.slug == tournament_slug)
        ids = list(session.exec(stmt).all())
        if len(ids) == 1:
            return ids[0]
        return None

    # Tier 1 — try each tagged tournament. First unambiguous hit wins.
    tour_slugs = [s for s in (video.tournament_slugs or "").split(",") if s]
    for tslug in tour_slugs:
        mid = _find(window_days=365, tournament_slug=tslug)
        if mid is not None:
            return mid

    # Tier 2 — drop the tournament constraint, tighten the window.
    mid = _find(window_days=14, tournament_slug=None)
    if mid is not None:
        return mid

    return None


def backfill_match_attribution(session: Session, limit: int = 200) -> int:
    """Probe VideoItem rows where match_id IS NULL but the tagging
    pass found 2+ players. Capped per run so a flood of new rows
    doesn't block sync. Returns count of rows newly attributed."""
    rows = session.exec(
        select(VideoItem)
        .where(VideoItem.match_id.is_(None))
        .where(VideoItem.player_slugs.is_not(None))
        .order_by(VideoItem.published_at.desc())
        .limit(limit)
    ).all()
    updated = 0
    for v in rows:
        mid = _attribute_to_match(session, v)
        if mid is None:
            continue
        v.match_id = mid
        session.add(v)
        updated += 1
    if updated:
        session.commit()
        log.info("match attribution: linked %d video(s)", updated)
    return updated


def retag_existing(
    session: Session,
    player_slugs: list[str],
    tournament_slugs: list[str],
) -> int:
    """Re-run _tag over every persisted VideoItem with the current
    player/tournament slug lists. Used after we tighten the tagging
    rules so old rows correct themselves. Returns count of rows whose
    tags actually changed."""
    rows = session.exec(select(VideoItem)).all()
    changed = 0
    for v in rows:
        new_ps, new_ts = _tag(v.title, player_slugs, tournament_slugs)
        new_ps = new_ps or None
        new_ts = new_ts or None
        if v.player_slugs != new_ps or v.tournament_slugs != new_ts:
            v.player_slugs = new_ps
            v.tournament_slugs = new_ts
            session.add(v)
            changed += 1
    if changed:
        session.commit()
        log.info("video retag: corrected %d row(s)", changed)
    return changed


def _tag(text: str, player_slugs: list[str], tournament_slugs: list[str]) -> tuple[str, str]:
    """Keyword-tag a video by player/tournament slug.

    We tag from the title ONLY — YouTube channel descriptions are
    promotional boilerplate (Tennis TV puts "the season-ending Nitto
    ATP Finals" in every description, which would tag every one of
    their videos with atp-finals). Title is precise enough; if
    coverage suffers we can revisit with a stop-word approach.
    """
    text_l = text.lower()
    # Dedup the input slug lists first — our tournaments table has one
    # row per (slug, year), so a single brand like atp-finals appears
    # many times in the input list and would otherwise multi-match.
    unique_players = list(dict.fromkeys(player_slugs))
    unique_tours = list(dict.fromkeys(tournament_slugs))
    matched_players = [s for s in unique_players if s.replace("-", " ") in text_l]
    matched_tours = [s for s in unique_tours if s.replace("-", " ") in text_l]
    return ",".join(matched_players[:5]), ",".join(matched_tours[:5])


def sync_videos(session: Session) -> list[VideoItem]:
    """Walk every configured channel feed; persist new VideoItems."""
    # Top-ranked players first so the cap actually contains the
    # players whose highlights are likely to appear. The naive
    # `limit(500)` without ORDER BY returned whichever 500 SQLite
    # happened to pick, sometimes excluding well-known names when the
    # players table is full of historical entries.
    player_slugs = list(session.exec(
        select(Player.slug)
        .where(Player.current_rank.is_not(None))
        .order_by(Player.current_rank)
        .limit(500)
    ).all())
    tournament_slugs = list(session.exec(select(Tournament.slug).limit(500)).all())

    # Re-tag existing rows on every sync run. Cheap (string scan over a
    # few hundred rows, no DB joins) and self-heals when we change the
    # tagging heuristic without needing a separate migration script.
    retag_existing(session, player_slugs, tournament_slugs)

    # Backfill orientation for any rows that haven't been probed yet
    # (rows from before this feature, or rows whose probe failed last
    # time). Capped per run so we don't block sync on a slow batch.
    backfill_orientation(session)

    # Backfill match-level attribution for rows where the tagger gave
    # us 2+ players. Re-runs every sync so videos posted before a
    # match was ingested eventually catch up.
    backfill_match_attribution(session)

    added: list[VideoItem] = []
    for source, channel_id in CHANNELS:
        url = _FEED_URL.format(cid=channel_id)
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            log.warning("video feed %s: parse crashed: %s", source, e)
            continue

        status = getattr(feed, "status", None)
        n_entries = len(feed.entries)
        feed_added = 0
        channel_name = (feed.feed.get("title") if hasattr(feed, "feed") else None) or None

        for entry in feed.entries:
            video_id = _video_id(entry)
            if not video_id:
                continue
            existing = session.exec(
                select(VideoItem).where(VideoItem.video_id == video_id)
            ).first()
            if existing:
                continue
            title = (entry.get("title") or "").strip()
            if not title:
                continue
            published = _parse_published(entry) or datetime.utcnow()
            summary = entry.get("summary") or entry.get("description")
            if isinstance(summary, str):
                summary = summary.strip() or None
            ps, ts = _tag(title, player_slugs, tournament_slugs)
            item = VideoItem(
                source=source,
                video_id=video_id,
                title=title,
                summary=summary,
                thumbnail_url=_thumbnail(entry, video_id),
                channel_name=channel_name,
                published_at=published,
                player_slugs=ps or None,
                tournament_slugs=ts or None,
                is_portrait=_probe_orientation(video_id),
            )
            # Try match attribution at insert time. The backfill loop
            # also picks it up later, but resolving here means it's
            # available the first time the row is returned.
            item.match_id = _attribute_to_match(session, item)
            session.add(item)
            added.append(item)
            feed_added += 1

        if n_entries == 0 or (status and status >= 400):
            log.warning(
                "video feed %s degraded: status=%s entries=%d",
                source, status, n_entries,
            )
        elif feed_added > 0:
            log.info(
                "video feed %s: %d new (of %d entries)",
                source, feed_added, n_entries,
            )

    session.commit()
    return added
