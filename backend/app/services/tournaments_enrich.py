"""Enrich tournaments with Wikipedia descriptions + images.

- Skips Challenger / ITF / Other (low signal, mostly no Wikipedia article)
- One enrichment attempt per tournament ever (enriched_at marks it tried)
- Polite rate-limit: 500ms between Wikipedia calls
- Trims extract to first paragraph (Wikipedia summaries are 1–4 paragraphs;
  we want a card-friendly blurb, not a wall of text).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

import httpx
from sqlmodel import Session, select

from app.models.tournament import Tournament, TournamentCategory
from app.services.wikidata import fetch_tournament_dates
from app.services.wikipedia import UA, fetch_summary

log = logging.getLogger(__name__)

ENRICH_CATEGORIES = {
    TournamentCategory.GRAND_SLAM,
    TournamentCategory.ATP_FINALS,
    TournamentCategory.WTA_FINALS,
    TournamentCategory.ATP_1000,
    TournamentCategory.WTA_1000,
    TournamentCategory.ATP_500,
    TournamentCategory.WTA_500,
    TournamentCategory.ATP_250,
    TournamentCategory.WTA_250,
    TournamentCategory.DAVIS_CUP,
    TournamentCategory.BJK_CUP,
}

_DELAY_S = 0.5  # politeness toward Wikipedia


def _trim_extract(text: str | None, max_chars: int = 480) -> str | None:
    if not text:
        return None
    # Take the first paragraph (Wikipedia summaries are double-spaced or sentence-end).
    para = text.split("\n\n")[0].strip()
    if len(para) <= max_chars:
        return para
    # Cut at sentence boundary near limit
    cut = para[:max_chars]
    last_period = cut.rfind(". ")
    if last_period > max_chars * 0.6:
        return cut[: last_period + 1]
    return cut.rstrip() + "…"


def _query_for(t: Tournament) -> str:
    """Build a search query that disambiguates well.

    Adding 'tennis' avoids matching the city/place article; '{name} Open'
    sometimes resolves to non-tennis events without it.
    """
    return f"{t.name} tennis tournament"


async def enrich_one(session: Session, tournament: Tournament, client: httpx.AsyncClient) -> bool:
    page = await fetch_summary(_query_for(tournament), client=client)
    tournament.enriched_at = datetime.utcnow()
    if page is None:
        session.add(tournament)
        session.commit()
        return False

    if page.extract:
        tournament.description = _trim_extract(page.extract)
    if page.image_url and not tournament.image_url:
        tournament.image_url = page.image_url
    if page.page_url:
        tournament.wikipedia_url = page.page_url
    session.add(tournament)
    session.commit()
    return True


async def enrich_pending(session: Session, max_count: int = 200) -> int:
    """Walk through unenriched top-tier tournaments, polite-rate."""
    candidates = session.exec(
        select(Tournament)
        .where(Tournament.enriched_at.is_(None))
        .where(Tournament.category.in_(ENRICH_CATEGORIES))
        .order_by(Tournament.year.desc())
        .limit(max_count)
    ).all()

    if not candidates:
        return 0

    enriched = 0
    async with httpx.AsyncClient(headers={"User-Agent": UA}, timeout=10.0) as client:
        for i, t in enumerate(candidates):
            try:
                if await enrich_one(session, t, client):
                    enriched += 1
            except Exception:
                log.exception("enrich failed for %s", t.slug)
            if i + 1 < len(candidates):
                await asyncio.sleep(_DELAY_S)

    log.info("tournament enrich: %d hits / %d tried", enriched, len(candidates))
    return enriched


async def enrich_dates_pending(session: Session, max_count: int = 200) -> int:
    """Populate Tournament.start_date / end_date from Wikidata P580/P582.

    Targets top-tier tournament editions that don't have a start_date set
    yet. Independent of description/image enrichment so we can backfill
    dates without re-fetching Wikipedia for already-enriched rows. Run on
    a daily cadence — dates rarely change mid-event but new editions get
    added throughout the year.
    """
    candidates = session.exec(
        select(Tournament)
        .where(Tournament.start_date.is_(None))
        .where(Tournament.category.in_(ENRICH_CATEGORIES))
        .order_by(Tournament.year.desc())
        .limit(max_count)
    ).all()

    if not candidates:
        return 0

    hits = 0
    async with httpx.AsyncClient(headers={"User-Agent": UA}, timeout=10.0) as client:
        for i, t in enumerate(candidates):
            try:
                dates = await fetch_tournament_dates(t.name, t.year, client=client)
                if dates and (dates.start_date or dates.end_date):
                    if dates.start_date:
                        t.start_date = dates.start_date
                    if dates.end_date:
                        t.end_date = dates.end_date
                    session.add(t)
                    session.commit()
                    hits += 1
            except Exception:
                log.exception("date enrich failed for %s %d", t.name, t.year)
            if i + 1 < len(candidates):
                await asyncio.sleep(_DELAY_S)

    log.info("tournament dates enrich: %d hits / %d tried", hits, len(candidates))
    return hits
