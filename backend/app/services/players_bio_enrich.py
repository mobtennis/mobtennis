"""Player bio enrichment via Wikipedia (using stored Wikidata IDs).

Pre-req: `Player.wikidata_id` is populated by `players_socials_enrich`.
Strategy:
  1. Fetch the Wikidata entity for the player's Q-id
  2. Read `sitelinks.enwiki` to get the canonical article title + URL
  3. Fetch the Wikipedia REST summary; trim its extract to a card-friendly blurb
  4. Persist `bio` + `wikipedia_url`

This avoids re-running the Wikipedia search per player — we already know exactly
which article to hit. Two HTTP calls per player.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

import httpx
from sqlmodel import Session, or_, select

from app.models.player import Player
from app.services.wikidata import UA, WIKIDATA_ENTITY_URL, WIKI_SUMMARY_URL

log = logging.getLogger(__name__)

_DELAY_S = 0.5
_MAX_BLURB = 480


def _trim_extract(text: str | None, max_chars: int = _MAX_BLURB) -> str | None:
    if not text:
        return None
    para = text.split("\n\n")[0].strip()
    if len(para) <= max_chars:
        return para
    cut = para[:max_chars]
    last_period = cut.rfind(". ")
    if last_period > max_chars * 0.6:
        return cut[: last_period + 1]
    return cut.rstrip() + "…"


async def _fetch_for_qid(qid: str, client: httpx.AsyncClient) -> tuple[str, str | None] | None:
    """Returns (wikipedia_title, wikipedia_url) for a Wikidata Q-id, via
    its enwiki sitelink. None if there's no English Wikipedia article."""
    er = await client.get(f"{WIKIDATA_ENTITY_URL}/{qid}.json")
    if er.status_code != 200:
        return None
    ent = er.json().get("entities", {}).get(qid, {})
    sitelink = ent.get("sitelinks", {}).get("enwiki", {})
    title = sitelink.get("title")
    url = sitelink.get("url")
    if not title:
        return None
    return title, url


async def enrich_one(session: Session, player: Player, client: httpx.AsyncClient) -> bool:
    if not player.wikidata_id:
        return False

    # Mark we tried so we don't loop forever on missing-article players.
    player.bio_enriched_at = datetime.utcnow()

    sitelink = await _fetch_for_qid(player.wikidata_id, client)
    if sitelink is None:
        session.add(player)
        session.commit()
        return False
    title, page_url = sitelink

    pr = await client.get(f"{WIKI_SUMMARY_URL}/{title.replace(' ', '_')}")
    if pr.status_code != 200:
        session.add(player)
        session.commit()
        return False
    summary = pr.json()
    extract = _trim_extract(summary.get("extract"))

    changed = False
    if extract and not player.bio:
        player.bio = extract
        changed = True
    if page_url and not player.wikipedia_url:
        player.wikipedia_url = page_url
        changed = True

    session.add(player)
    session.commit()
    return changed


async def enrich_pending(session: Session, max_count: int = 200) -> tuple[int, int]:
    """Walk players that have a Wikidata ID but no bio yet."""
    candidates = session.exec(
        select(Player)
        .where(Player.wikidata_id.is_not(None))
        .where(or_(Player.bio.is_(None), Player.bio == ""))
        .where(Player.bio_enriched_at.is_(None))
        .order_by(Player.current_rank.is_(None), Player.current_rank)
        .limit(max_count)
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
                log.exception("bio enrich failed for %s", p.slug)
            if i + 1 < len(candidates):
                await asyncio.sleep(_DELAY_S)

    log.info("player bio enrich: %d updated / %d tried", succeeded, len(candidates))
    return len(candidates), succeeded
