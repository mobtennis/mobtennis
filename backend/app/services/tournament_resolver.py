"""Canonical tournament resolution.

Tournaments arrive into the catalog from two ingest paths that name the
same brand differently:

  - Sackmann CSVs use the historical / commonly indexed form:
    "Roland Garros", "Tour Finals", "Australian Open"
  - api-tennis uses the marketing / English form:
    "French Open", "ATP Finals", "Australian Open"

Without intervention, the slugifier produces two slugs for the same
brand (`roland-garros` from history + `french-open` from this year's
live feed) and the per-brand page only sees half the story. This module
mirrors the player-resolution shape we already use for Wikipedia bracket
imports:

  wiki_brackets_overrides.py   — static Wikipedia-title → player-slug map
  wiki_brackets_apply.py       — `_candidate_slugs()` + `resolve_player()`

  tournament_resolver.py       — `BRAND_ALIASES` + `canonical_slug()` +
                                 `resolve_tournament()` + `merge_duplicates()`

Use:
  - INGEST PATHS (`services/sync.py`, `services/tournaments_catalog.py`)
    call `canonical_slug(name)` instead of `slugify(name)`. This means
    every new row written to the DB uses the canonical brand slug from
    the start.
  - URL ROUTING (`api/tournaments.py`) can call `resolve_tournament()`
    when the inbound slug might be an alias the user has bookmarked,
    so /tournaments/atp/french-open still resolves to the canonical
    row even after the slug is canonicalised.
  - DATA CLEANUP can call `merge_duplicates()` to consolidate existing
    alias rows into the canonical row (run once after seeding a new
    alias entry).
"""

from __future__ import annotations

import logging

from slugify import slugify
from sqlmodel import Session, select

from app.models.match import Match
from app.models.tournament import Tournament

log = logging.getLogger(__name__)


# Canonical slug → set of slugified aliases that should resolve to it.
# Aliases are stored LOWERCASED + slugified (post-`slugify(name)` shape),
# so the lookup is a direct dict hit without re-canonicalising.
#
# To grow this table:
#   1. Find the divergence — usually surfaces as two adjacent brand pages
#      on the /tournaments index, or as missing history on one of them.
#   2. Pick the canonical slug (prefer the one with more years of history).
#   3. Add the divergent slugs to the alias set.
#   4. Run `scripts/merge_tournament_aliases.py` once to consolidate
#      existing rows — see merge_duplicates() below.
BRAND_ALIASES: dict[str, set[str]] = {
    # Slams: prefer the historical / Sackmann names since they carry
    # decades of finals.
    "roland-garros":      {"french-open", "rolandgarros"},
    # Year-end Finals — Sackmann uses the abbreviated brand, api-tennis
    # the sponsored / marketing name.
    "atp-finals":         {"tour-finals", "nitto-atp-finals", "atp-tour-finals"},
    "wta-finals":         {"wta-tour-finals", "wta-year-end-finals"},
    # Sources caught by scripts/find_tournament_collisions.py:
    "naples":             {"napoli"},
    "nextgen-finals":     {"next-gen-finals", "next-gen-finals-jeddah"},
}


# Inverted lookup, built once at import time.
_ALIAS_TO_CANONICAL: dict[str, str] = {}
for _canonical, _aliases in BRAND_ALIASES.items():
    for _alias in _aliases:
        _ALIAS_TO_CANONICAL[_alias] = _canonical


def canonical_slug(name: str) -> str:
    """Slugify `name`, then redirect through the alias table.

    Called by the ingest paths so every new row lands on the canonical
    brand slug. Truncated to 80 chars to match the existing column
    width.
    """
    raw = slugify(name)[:80]
    return _ALIAS_TO_CANONICAL.get(raw, raw)


def is_alias_of(slug: str, canonical: str) -> bool:
    """True if `slug` is a known alias of `canonical` (or equal)."""
    return slug == canonical or _ALIAS_TO_CANONICAL.get(slug) == canonical


def resolve_tournament(
    session: Session, slug: str, year: int, tour,
) -> Tournament | None:
    """Find a Tournament row, accepting the canonical slug OR any known alias.

    Used by URL routing — a user bookmarked /tournaments/atp/french-open
    when the catalog was creating that slug; after canonicalisation the
    row is at /tournaments/atp/roland-garros but we still want the old
    URL to resolve.
    """
    target = _ALIAS_TO_CANONICAL.get(slug, slug)
    return session.exec(
        select(Tournament).where(
            Tournament.slug == target,
            Tournament.year == year,
            Tournament.tour == tour,
        )
    ).first()


def merge_duplicates(session: Session) -> dict:
    """One-shot data cleanup: walk every alias, find rows still living at
    the alias slug, reassign their matches to the canonical row (or move
    the row onto the canonical slug if no canonical row exists), then
    delete the alias row.

    Idempotent. Safe to run repeatedly — re-runs after the first do
    nothing because no more alias-slug rows exist.

    Returns a summary dict: `{"merged": N, "renamed": M, "matches_moved": K}`.
    """
    merged = renamed = matches_moved = 0

    for canonical, aliases in BRAND_ALIASES.items():
        for alias in aliases:
            alias_rows = session.exec(
                select(Tournament).where(Tournament.slug == alias)
            ).all()
            for alias_row in alias_rows:
                target = session.exec(
                    select(Tournament).where(
                        Tournament.slug == canonical,
                        Tournament.year == alias_row.year,
                        Tournament.tour == alias_row.tour,
                    )
                ).first()
                if target is None:
                    # No canonical sibling exists — just rename in place.
                    alias_row.slug = canonical
                    session.add(alias_row)
                    renamed += 1
                    log.info(
                        "renamed tournament id=%s slug=%s → %s for %s/%s",
                        alias_row.id, alias, canonical,
                        alias_row.tour, alias_row.year,
                    )
                    continue
                # Reassign matches, then delete the alias row.
                match_rows = session.exec(
                    select(Match).where(Match.tournament_id == alias_row.id)
                ).all()
                for m in match_rows:
                    m.tournament_id = target.id
                    session.add(m)
                    matches_moved += 1
                # Promote any metadata the canonical row is missing.
                for field in (
                    "city", "country_code", "start_date", "end_date",
                    "draw_size", "prize_money", "wikipedia_url",
                    "description", "image_url", "api_tennis_id",
                ):
                    if getattr(target, field, None) is None:
                        v = getattr(alias_row, field, None)
                        if v is not None:
                            setattr(target, field, v)
                session.add(target)
                session.delete(alias_row)
                merged += 1
                log.info(
                    "merged tournament id=%s (slug=%s) into id=%s (slug=%s) "
                    "— %d matches moved",
                    alias_row.id, alias, target.id, canonical, len(match_rows),
                )
    session.commit()
    return {"merged": merged, "renamed": renamed, "matches_moved": matches_moved}
