"""Scheduler entry point for the new Wikipedia bracket pipeline.

Find tournaments worth scraping right now (live or just-finished
Slam/Masters/Finals tier), pull each one's wikitext, parse, reconcile.
Reuses wiki_brackets.parse_wikitext (sync) and wiki_brackets_apply
.apply_parsed_bracket (sync against a DB session).

Cadence rationale (`scrape_pending_brackets` is meant to be called from
the scheduler every ~30 min during a live tournament). The Wikipedia
editor lag for "match just finished" → "bracket updated" is typically
10-30 minutes; scraping any faster wastes requests on unchanged pages.

Crucially: NEVER passes `nuke_first=True`. The scheduler is incremental
maintenance — apply_parsed_bracket's normal upsert path is idempotent
and only writes fields where Wikipedia has authoritative data.
"""

from __future__ import annotations

import asyncio
import gc
import logging
from datetime import date, timedelta

import httpx
from sqlmodel import Session, select

from app.db.session import engine
from app.models.match import Match
from app.models.tournament import Tournament
from app.services.wiki_brackets import fetch_wikitext, parse_wikitext
from app.services.wiki_brackets_apply import apply_parsed_bracket
from app.services.wiki_brackets_titles import SCRAPABLE_CATEGORIES, wiki_title_for

log = logging.getLogger(__name__)


def _candidate_tournaments(session: Session) -> list[Tournament]:
    """Tournaments worth scraping right now.

    Same shape as the live/today logic in the tournaments-index endpoint:
      - currently in their date window, OR
      - finished within the last 7 days (to catch late wiki corrections)
    Restricted to categories the parser handles (SCRAPABLE_CATEGORIES).
    Capped to a sane number so a runaway query can't pin the scheduler.
    """
    today = date.today()
    recent_cutoff = today - timedelta(days=7)
    upcoming_cutoff = today + timedelta(days=14)

    rows = session.exec(
        select(Tournament)
        .where(Tournament.category.in_(list(SCRAPABLE_CATEGORIES)))
        .where(
            (Tournament.start_date.is_(None))
            | (
                (Tournament.start_date <= upcoming_cutoff)
                & (
                    (Tournament.end_date.is_(None))
                    | (Tournament.end_date >= recent_cutoff)
                )
            )
        )
        .order_by(Tournament.year.desc())
        .limit(30)
    ).all()
    return rows


async def _fetch_async(page_title: str) -> str | None:
    """Async wrapper around the sync fetch_wikitext, since the parser
    module uses httpx.Client. The scheduler runs in an event loop; we
    do the network IO in a thread to avoid blocking it."""
    return await asyncio.to_thread(fetch_wikitext, page_title)


async def scrape_pending_brackets() -> dict:
    """Run the new pipeline against every candidate tournament.

    Per-tournament work is memory-bounded (~ a few hundred KB of wikitext
    + transient parser objects). We gc.collect() + sleep briefly between
    tournaments — same belt-and-braces we added to the old scraper when
    a back-to-back run was pushing the 2 GB box into memory pressure.
    """
    with Session(engine) as session:
        candidates = _candidate_tournaments(session)

    total_updated = 0
    total_created = 0
    total_unresolved = 0
    pages_done = 0

    for t in candidates:
        page = wiki_title_for(t)
        if page is None:
            continue
        try:
            wikitext = await _fetch_async(page)
        except Exception as e:
            log.warning("wiki fetch failed for %s: %s", page, e)
            continue
        if wikitext is None:
            # Page doesn't exist yet (draw not announced) — fine, skip.
            continue
        parsed = parse_wikitext(page, wikitext)
        if not parsed.matches:
            continue

        # DB work in a fresh session per tournament so a transient failure
        # doesn't taint the rest of the run.
        with Session(engine) as session:
            t_fresh = session.get(Tournament, t.id)
            if t_fresh is None:
                continue
            try:
                result = apply_parsed_bracket(session, t_fresh, parsed, nuke_first=False)
                session.commit()
            except Exception:
                log.exception("wiki apply failed for %s/%s/%s",
                              t_fresh.tour.value, t_fresh.slug, t_fresh.year)
                continue
            total_updated += result.updated
            total_created += result.created
            total_unresolved += len(result.unresolved)
            pages_done += 1
            if result.unresolved:
                # Log unresolved with dedup so the same name doesn't spam
                # every run — these are signals to grow the overrides table.
                distinct = sorted({w for w, _ in result.unresolved})
                for wikilink in distinct[:5]:
                    log.warning("wiki bracket: unresolved player %r for %s",
                                wikilink, page)
                if len(distinct) > 5:
                    log.warning("wiki bracket: %d more unresolved players for %s",
                                len(distinct) - 5, page)

        gc.collect()
        await asyncio.sleep(0.5)

    summary = {
        "pages": pages_done,
        "created": total_created,
        "updated": total_updated,
        "unresolved": total_unresolved,
    }
    log.info(
        "wiki brackets: scraped %d page(s); created=%d updated=%d unresolved=%d",
        pages_done, total_created, total_updated, total_unresolved,
    )
    return summary
