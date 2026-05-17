"""Discover Instagram + Twitter handles for the top-N ranked players.

Walks players ordered by `current_rank` (top-200 by default), running
Wikidata discovery for any that haven't been enriched in `STALE_DAYS`.
Polite-rate-limits by sleeping `_DELAY_S` between players.

Designed to be re-run on a schedule — rankings change, players retire,
new players enter the top 200, handles change. Idempotent: nothing
gets re-fetched within the staleness window.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

import httpx
from sqlmodel import Session, or_, select

from app.models.player import Player
from app.services.wikidata import UA, fetch_player_socials

log = logging.getLogger(__name__)

_DELAY_S = 0.5
STALE_DAYS = 90
DEFAULT_TOP_N = 200


async def enrich_one(session: Session, player: Player, client: httpx.AsyncClient) -> bool:
    socials = await fetch_player_socials(player.full_name, client=client)
    player.socials_enriched_at = datetime.utcnow()
    if socials is None:
        session.add(player)
        session.commit()
        return False

    changed = False
    if socials.wikidata_id and player.wikidata_id != socials.wikidata_id:
        player.wikidata_id = socials.wikidata_id
        changed = True
    if socials.instagram and player.instagram_handle != socials.instagram:
        player.instagram_handle = socials.instagram
        changed = True
    if socials.twitter and player.twitter_handle != socials.twitter:
        player.twitter_handle = socials.twitter
        changed = True

    session.add(player)
    session.commit()
    return changed


async def enrich_top_n(session: Session, top_n: int = DEFAULT_TOP_N) -> tuple[int, int]:
    """Returns (tried, succeeded)."""
    cutoff = datetime.utcnow() - timedelta(days=STALE_DAYS)

    candidates = session.exec(
        select(Player)
        .where(Player.current_rank.is_not(None))
        .where(Player.current_rank <= top_n)
        .where(or_(Player.socials_enriched_at.is_(None), Player.socials_enriched_at < cutoff))
        .order_by(Player.current_rank)
    ).all()

    if not candidates:
        return 0, 0

    succeeded = 0
    async with httpx.AsyncClient(headers={"User-Agent": UA}, timeout=10.0) as client:
        for i, p in enumerate(candidates):
            try:
                if await enrich_one(session, p, client):
                    succeeded += 1
            except Exception:
                log.exception("socials enrich failed for %s", p.slug)
            if i + 1 < len(candidates):
                await asyncio.sleep(_DELAY_S)

    log.info("socials enrich: %d updated / %d tried (top %d)", succeeded, len(candidates), top_n)
    return len(candidates), succeeded
