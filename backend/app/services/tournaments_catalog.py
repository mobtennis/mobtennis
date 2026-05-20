"""Seed the Tournament table with every brand the provider knows about.

Without this, /tournaments only shows brands that have had matches in the last
14 days. With it, you see Roland Garros, Wimbledon, US Open, all 1000s, all
500s, etc. — the full Fotmob-style catalog.

Storage strategy: each brand becomes one Tournament row at year=current_year
as a placeholder. When real fixtures arrive for that year, sync_live() upserts
into the same row by (slug, year, tour) — so we don't end up with stale
placeholders next to a real season.
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from app.services.tournament_resolver import canonical_slug
from sqlmodel import Session, select

from app.models.player import Tour
from app.models.tournament import Tournament
from app.services.categorize import categorize, tier_weight
from app.services.live.base import TournamentMeta

log = logging.getLogger(__name__)


def _strip_tour_prefix(name: str) -> str:
    """api-tennis publishes both 'Australian Open' and 'ATP Australian Open'
    as separate catalog entries — collapse them since the tour is stored
    separately on the row."""
    n = name.strip()
    for prefix in ("ATP ", "WTA ", "Atp ", "Wta "):
        if n.startswith(prefix):
            return n[len(prefix):].strip()
    return n


def cleanup_prefixed_brands(session: Session) -> int:
    """One-shot: collapse 'ATP Foo' / 'WTA Foo' rows into 'Foo'.

    api-tennis publishes both forms as distinct catalog entries; we want one
    canonical row per (slug, year, tour). On collision, match references
    migrate to the canonical row before the prefixed row is deleted.
    """
    from app.models.match import Match

    merged = 0
    for t in session.exec(select(Tournament)).all():
        clean_name = _strip_tour_prefix(t.name)
        if clean_name == t.name:
            continue
        new_slug = canonical_slug(clean_name)
        if new_slug == t.slug:
            t.name = clean_name
            session.add(t)
            merged += 1
            continue

        existing = session.exec(
            select(Tournament).where(
                Tournament.slug == new_slug,
                Tournament.year == t.year,
                Tournament.tour == t.tour,
            )
        ).first()
        if existing and existing.id != t.id:
            for m in session.exec(select(Match).where(Match.tournament_id == t.id)).all():
                m.tournament_id = existing.id
                session.add(m)
            session.delete(t)
            merged += 1
        else:
            t.slug = new_slug
            t.name = clean_name
            session.add(t)
            merged += 1

    session.commit()
    return merged


def upsert_catalog(session: Session, items: list[TournamentMeta]) -> tuple[int, int]:
    """Returns (added, updated) counts."""
    if not items:
        return 0, 0

    year = date.today().year
    added = 0
    updated = 0

    # Singles is preferred over doubles when both exist for the same brand —
    # iterate singles-first so the (slug, year, tour) row carries the singles id.
    items_sorted = sorted(items, key=lambda i: (i.is_doubles, i.name))

    for it in items_sorted:
        try:
            tour = Tour(it.tour)
        except ValueError:
            continue

        clean_name = _strip_tour_prefix(it.name)
        slug = canonical_slug(clean_name)
        if not slug:
            continue

        existing = session.exec(
            select(Tournament).where(
                Tournament.slug == slug,
                Tournament.year == year,
                Tournament.tour == tour,
            )
        ).first()

        if existing:
            changed = False
            if it.surface and not existing.surface:
                existing.surface = it.surface
                changed = True
            if it.external_id and not existing.api_tennis_id and not it.is_doubles:
                existing.api_tennis_id = it.external_id
                changed = True
            new_cat = categorize(it.name, tour, event_type=it.event_type)
            # api-tennis emits multiple catalog entries with the same name —
            # e.g. the WTA 1000 "Rome" and a Challenger "Rome" are different
            # physical events. They collide on (slug, year, tour) here. Only
            # accept the new tier if it's an upgrade (lower tier_weight =
            # higher tier) so the marquee event isn't downgraded by a
            # same-named lesser one ingested later.
            if existing.category != new_cat and tier_weight(new_cat) <= tier_weight(existing.category):
                existing.category = new_cat
                changed = True
            if changed:
                existing.updated_at = datetime.utcnow()
                session.add(existing)
                updated += 1
        else:
            session.add(
                Tournament(
                    slug=slug,
                    year=year,
                    name=clean_name,
                    tour=tour,
                    category=categorize(clean_name, tour, event_type=it.event_type),
                    surface=it.surface,
                    api_tennis_id=it.external_id if not it.is_doubles else None,
                )
            )
            added += 1

        if (added + updated) % 500 == 0:
            session.commit()

    session.commit()
    return added, updated
