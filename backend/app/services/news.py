"""RSS news aggregation.

Pulls the configured feeds, dedupes by source_url, persists.
Tagging (player/tournament) is keyword-based for v1.

Curated to feeds that are confirmed alive — `scripts/probe_news_feeds.py`
runs feedparser against each candidate and reports entry counts. Dropped
in May 2026: atptour (now 403s on the RSS endpoint), wta (404), tennis.com
(no longer publishes RSS), reuters (URL retired).
"""

import logging
import re
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from time import mktime

import feedparser
from sqlmodel import Session, select

from app.models.news import NewsItem
from app.models.player import Player
from app.models.tournament import Tournament

log = logging.getLogger(__name__)

FEEDS: list[tuple[str, str]] = [
    ("espn",               "https://www.espn.com/espn/rss/tennis/news"),
    ("the-tennis-podcast", "https://thetennispodcast.libsyn.com/rss"),
    ("guardian",           "https://www.theguardian.com/sport/tennis/rss"),
    ("bbc",                "https://feeds.bbci.co.uk/sport/tennis/rss.xml"),
    ("tennis365",          "https://www.tennis365.com/feed"),
]


def _parse_published(entry: dict) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return datetime.fromtimestamp(mktime(parsed))


def _tag(text: str, player_slugs: list[str], tournament_slugs: list[str]) -> tuple[str, str]:
    text_l = text.lower()
    matched_players = [s for s in player_slugs if s.replace("-", " ") in text_l]
    matched_tours = [s for s in tournament_slugs if s.replace("-", " ") in text_l]
    return ",".join(matched_players[:5]), ",".join(matched_tours[:5])


def sync_news(session: Session) -> list[NewsItem]:
    """Pulls every feed, persists new items. Returns the newly-added rows so
    the caller can fan them out as push notifications to followers."""
    # Top-ranked players first so the 500-cap reliably contains the
    # players whose news is likely to appear. Without ORDER BY the
    # naive limit() returned whichever 500 SQLite picked, sometimes
    # excluding current top-10 names on DBs with long historical tails.
    # Single-column selects return scalars, not row objects.
    player_slugs = list(session.exec(
        select(Player.slug)
        .where(Player.current_rank.is_not(None))
        .order_by(Player.current_rank)
        .limit(500)
    ).all())
    tournament_slugs = list(session.exec(select(Tournament.slug).limit(500)).all())

    added: list[NewsItem] = []
    # Per-feed visibility — log a one-line summary even when we add
    # nothing. That way a feed that silently dies (404 / empty XML)
    # shows up in the journal as "entries=0" and we notice without
    # waiting for a user to complain.
    for source, url in FEEDS:
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            log.warning("news feed %s: parse crashed: %s", source, e)
            continue
        status = getattr(feed, "status", None)
        n_entries = len(feed.entries)
        feed_added = 0
        for entry in feed.entries:
            link = entry.get("link")
            if not link:
                continue
            existing = session.exec(select(NewsItem).where(NewsItem.source_url == link)).first()
            if existing:
                continue
            published = _parse_published(entry) or datetime.utcnow()
            haystack = f"{entry.get('title', '')} {entry.get('summary', '')}"
            ps, ts = _tag(haystack, player_slugs, tournament_slugs)
            item = NewsItem(
                source=source,
                source_url=link,
                title=entry.get("title", ""),
                summary=entry.get("summary"),
                image_url=_extract_image(entry),
                author=entry.get("author"),
                published_at=published,
                player_slugs=ps or None,
                tournament_slugs=ts or None,
            )
            session.add(item)
            added.append(item)
            feed_added += 1
        if n_entries == 0 or (status and status >= 400):
            log.warning(
                "news feed %s degraded: status=%s entries=%d",
                source, status, n_entries,
            )
        elif feed_added > 0:
            log.info(
                "news feed %s: %d new (of %d entries)",
                source, feed_added, n_entries,
            )
    session.commit()
    return added


def _extract_image(entry: dict) -> str | None:
    media = entry.get("media_content") or entry.get("media_thumbnail")
    if media and isinstance(media, list) and media[0].get("url"):
        return media[0]["url"]
    for link in entry.get("links", []):
        if link.get("type", "").startswith("image"):
            return link.get("href")
    return None


# RSS feeds ship `summary` as HTML — paragraphs, anchor tags, sometimes embedded
# images. We want plain text for the card blurb and a fallback image if the feed
# didn't supply one in media_content. Stdlib-only so we don't add a dep.
class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.first_img: str | None = None
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self._skip_depth += 1
            return
        if tag == "img" and self.first_img is None:
            for k, v in attrs:
                if k == "src" and v:
                    self.first_img = v
                    break

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self.parts.append(data)


def clean_summary(raw: str | None, max_len: int = 280) -> tuple[str | None, str | None]:
    """Return (plain_text, fallback_image_url) extracted from an RSS summary.

    Returns (None, None) if the input is empty or only whitespace.
    """
    if not raw:
        return None, None
    parser = _TextExtractor()
    try:
        parser.feed(raw)
    except Exception:
        # Malformed HTML — fall back to a regex strip so we still return text.
        text = re.sub(r"<[^>]+>", " ", raw)
        text = unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        return (text[:max_len].rstrip() + "…") if len(text) > max_len else (text or None), None
    text = unescape("".join(parser.parts))
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None, parser.first_img
    if len(text) > max_len:
        text = text[:max_len].rstrip() + "…"
    return text, parser.first_img
