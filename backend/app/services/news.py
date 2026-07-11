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
from io import BytesIO
from time import mktime

import feedparser
import httpx
from PIL import Image
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
    # Cap live og:image fetches per run so a feed that dumps many new
    # items at once can't stall the 15-min job on network round-trips.
    og_budget = 12
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
            image = _extract_image(entry)
            if not image and og_budget > 0:
                image = fetch_og_image(link)
                og_budget -= 1
            item = NewsItem(
                source=source,
                source_url=link,
                title=entry.get("title", ""),
                summary=entry.get("summary"),
                image_url=image,
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
    """Image straight from the feed entry — media_content / media_thumbnail
    / an image-typed <link>. Cheap (no network). Returns None when the feed
    carries no image, in which case callers can fall back to og:image via
    `fetch_og_image(link)`."""
    media = entry.get("media_content") or entry.get("media_thumbnail")
    if media and isinstance(media, list) and media[0].get("url"):
        return media[0]["url"]
    for link in entry.get("links", []):
        if link.get("type", "").startswith("image"):
            return link.get("href")
    # Some feeds embed the lead image only in the summary HTML.
    _, summary_img = clean_summary(entry.get("summary"))
    return summary_img


# og:image / twitter:image meta tags, in either attribute order.
_OG_IMAGE_RE = (
    re.compile(
        r'<meta[^>]+(?:property|name)=["\'](?:og:image(?::url)?|twitter:image)["\']'
        r'[^>]+content=["\']([^"\']+)["\']',
        re.I,
    ),
    re.compile(
        r'<meta[^>]+content=["\']([^"\']+)["\']'
        r'[^>]+(?:property|name)=["\'](?:og:image(?::url)?|twitter:image)["\']',
        re.I,
    ),
)


def fetch_og_image(url: str, *, timeout: float = 6.0) -> str | None:
    """Fetch a news article's og:image — the image the publisher itself
    designates for social/RSS previews. Displayed with a visible source
    credit and a link back to the article, this is the standard,
    publisher-intended syndication use (what every RSS reader / unfurler
    does). Returns None on any failure so callers degrade gracefully."""
    if not url or not url.startswith("http"):
        return None
    try:
        r = httpx.get(
            url,
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; MobTennisBot/1.0; +https://mob.tennis)"
            },
        )
        r.raise_for_status()
        head = r.text[:200_000]  # og tags live in <head>; cap the parse
    except Exception:
        return None
    for rx in _OG_IMAGE_RE:
        m = rx.search(head)
        if m:
            img = unescape(m.group(1)).strip()
            if img.startswith("http"):
                return img
    return None


# A featured image renders at roughly article width (~700-1200px), so a
# small feed thumbnail (e.g. the Guardian's 140px RSS variant) looks
# grainy when upscaled. Require a real, non-tiny source image: short edge
# ≥ 400 AND long edge ≥ 700. Orientation-agnostic so portraits pass too.
_MIN_IMAGE_SHORT_EDGE = 400
_MIN_IMAGE_LONG_EDGE = 700


def resolution_ok(size: tuple[int, int] | None) -> bool:
    if not size:
        return False
    w, h = size
    return min(w, h) >= _MIN_IMAGE_SHORT_EDGE and max(w, h) >= _MIN_IMAGE_LONG_EDGE


def measure_image(url: str, *, timeout: float = 6.0) -> tuple[int, int] | None:
    """(width, height) of the image at `url`, or None on any failure.
    Used to reject low-resolution / grainy images before we feature one."""
    if not url or not url.startswith("http"):
        return None
    try:
        r = httpx.get(
            url,
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; MobTennisBot/1.0; +https://mob.tennis)"
            },
        )
        r.raise_for_status()
        with Image.open(BytesIO(r.content)) as im:
            return im.size
    except Exception:
        return None


# Wikimedia thumb URLs carry the width as ".../<N>px-<File>". Bump it so a
# small player thumb becomes a crisp source before we feature it.
_COMMONS_THUMB_RE = re.compile(r"/(\d+)px-")


def upsize_commons(url: str | None, target: int = 1024) -> str | None:
    if not url:
        return url
    return _COMMONS_THUMB_RE.sub(f"/{target}px-", url, count=1)


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
