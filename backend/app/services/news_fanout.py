"""Fan freshly-ingested news items out to player + tournament followers.

Called from the scheduler right after `sync_news` returns the new rows.
We dedupe per-user-per-news so someone following both Sinner and Wimbledon
gets one push for an article tagged with both, not two.

Player-perspective wording wins over tournament-perspective for the same
user, since "news about your favorite player" feels more relevant than
"news about a tournament you follow".
"""

from __future__ import annotations

import logging

from sqlmodel import Session, select

from app.db.session import engine
from app.models.follow import Follow, FollowKind
from app.models.news import NewsItem
from app.models.player import Player
from app.models.push_token import PushToken
from app.models.tournament import Tournament
from app.services.push import send_push

log = logging.getLogger(__name__)

# News article body cap — keeps the push notification readable on lock screen.
_BODY_MAX = 140


async def fan_out(item_ids: list[int]) -> int:
    """Send push notifications for the given news item IDs.

    All DB reads happen in a single tight session block; HTTP send_push
    calls run afterwards with no connection held. Earlier this function
    held a session through every Expo round-trip, which contributed to
    pool exhaustion under load.
    """
    if not item_ids:
        return 0

    # Phase 1: build all outbound batches with the session open.
    batches: list[list[dict]] = []
    with Session(engine) as session:
        items = session.exec(select(NewsItem).where(NewsItem.id.in_(item_ids))).all()
        if not items:
            return 0

        # Cache slug → display-name lookups. News fan-out can touch many players /
        # tournaments per cycle — fetching each one separately gets expensive.
        player_names = _player_name_cache(session, items)
        tournament_names = _tournament_name_cache(session, items)

        for item in items:
            player_slugs = _split(item.player_slugs)
            tournament_slugs = _split(item.tournament_slugs)
            if not player_slugs and not tournament_slugs:
                continue

            # user_token → message dict. Player perspective takes priority over
            # tournament perspective when the same user follows both.
            msgs: dict[str, dict] = {}

            for slug in player_slugs:
                for ut in _player_followers(session, slug):
                    if ut in msgs:
                        continue
                    name = player_names.get(slug) or _humanize(slug)
                    msgs[ut] = {
                        "title": f"{name} in the news",
                        "body": _truncate(item.title, _BODY_MAX),
                        "data": {"news_id": item.id, "via": "player", "slug": slug},
                    }

            for slug in tournament_slugs:
                for ut in _tournament_followers(session, slug):
                    if ut in msgs:
                        continue
                    name = tournament_names.get(slug) or _humanize(slug)
                    msgs[ut] = {
                        "title": f"{name}",
                        "body": _truncate(item.title, _BODY_MAX),
                        "data": {"news_id": item.id, "via": "tournament", "slug": slug},
                    }

            if not msgs:
                continue

            push_tokens = session.exec(
                select(PushToken).where(PushToken.user_token.in_(list(msgs.keys())))
            ).all()
            if not push_tokens:
                continue

            batch = []
            for pt in push_tokens:
                m = msgs.get(pt.user_token)
                if not m:
                    continue
                batch.append({
                    "to": pt.expo_token,
                    "title": m["title"],
                    "body": m["body"],
                    "data": m["data"],
                    "sound": "default",
                })
            if batch:
                batches.append(batch)

    # Phase 2: HTTP without any DB connection held.
    sent = 0
    for batch in batches:
        try:
            await send_push(batch)
            sent += len(batch)
        except Exception:
            log.exception("news fan-out send failed for batch of %d", len(batch))

    return sent


def _split(s: str | None) -> list[str]:
    if not s:
        return []
    return [p for p in s.split(",") if p]


def _player_followers(session: Session, slug: str) -> list[str]:
    rows = session.exec(
        select(Follow).where(
            Follow.kind == FollowKind.PLAYER,
            Follow.target_slug == slug,
        )
    ).all()
    return [r.user_token for r in rows]


def _tournament_followers(session: Session, slug: str) -> list[str]:
    rows = session.exec(
        select(Follow).where(
            Follow.kind == FollowKind.TOURNAMENT,
            Follow.target_slug == slug,
        )
    ).all()
    return [r.user_token for r in rows]


def _player_name_cache(session: Session, items: list[NewsItem]) -> dict[str, str]:
    slugs: set[str] = set()
    for item in items:
        slugs.update(_split(item.player_slugs))
    if not slugs:
        return {}
    rows = session.exec(select(Player).where(Player.slug.in_(list(slugs)))).all()
    return {p.slug: p.full_name for p in rows}


def _tournament_name_cache(session: Session, items: list[NewsItem]) -> dict[str, str]:
    slugs: set[str] = set()
    for item in items:
        slugs.update(_split(item.tournament_slugs))
    if not slugs:
        return {}
    # Multiple tournaments share a slug across years; pick any name (they
    # share the brand name across years anyway).
    rows = session.exec(select(Tournament).where(Tournament.slug.in_(list(slugs)))).all()
    out: dict[str, str] = {}
    for t in rows:
        out.setdefault(t.slug, t.name)
    return out


def _humanize(slug: str) -> str:
    return slug.replace("-", " ").title()


def _truncate(text: str, n: int) -> str:
    if len(text) <= n:
        return text
    return text[: n - 1].rstrip() + "…"
