"""Persist provider rankings into Player + Ranking tables.

- Upserts Player by api_tennis_id then by (slug, tour)
- Inserts a Ranking row for the current week (idempotent — skips dupes)
- Updates Player.current_rank and career_high_rank
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from slugify import slugify
from sqlmodel import Session, select

from app.models.player import Player, Tour
from app.models.ranking import Ranking
from app.services.countries import name_to_iso3
from app.services.live.base import RankingEntry
from app.services.player_dedup import find_player_by_name, name_key


def _week_floor(d: date) -> date:
    """Snap to Monday — ATP/WTA rankings publish weekly on Mondays."""
    return d - timedelta(days=d.weekday())


def _upsert_player(session: Session, entry: RankingEntry, tour: Tour) -> Player:
    if entry.player_external_id:
        existing = session.exec(
            select(Player).where(Player.api_tennis_id == entry.player_external_id)
        ).first()
        if existing:
            if existing.name_key is None:
                existing.name_key = name_key(existing.full_name)
                session.add(existing)
            return existing

    # Order-insensitive name match before slug lookup — catches the case
    # where one source serializes "Thiago Agustin Tirante" and another
    # ships "Agustin Tirante Thiago" before either creates a duplicate.
    by_name = find_player_by_name(session, entry.player_name, tour)
    if by_name:
        if entry.player_external_id and not by_name.api_tennis_id:
            by_name.api_tennis_id = entry.player_external_id
            session.add(by_name)
        return by_name

    slug = slugify(entry.player_name)[:80] or f"player-{entry.player_external_id}"
    by_slug = session.exec(
        select(Player).where(Player.slug == slug, Player.tour == tour)
    ).first()
    if by_slug:
        if entry.player_external_id and not by_slug.api_tennis_id:
            by_slug.api_tennis_id = entry.player_external_id
            session.add(by_slug)
        if by_slug.name_key is None:
            by_slug.name_key = name_key(by_slug.full_name)
            session.add(by_slug)
        return by_slug

    if session.exec(select(Player).where(Player.slug == slug)).first():
        slug = f"{slug}-{entry.player_external_id or 'x'}"

    p = Player(
        slug=slug,
        full_name=entry.player_name,
        tour=tour,
        country_code=name_to_iso3(entry.country_name),
        api_tennis_id=entry.player_external_id,
        name_key=name_key(entry.player_name),
    )
    session.add(p)
    session.flush()
    return p


def upsert_rankings(session: Session, entries: list[RankingEntry]) -> int:
    """Returns count of ranking rows inserted (existing rows for the week are skipped)."""
    if not entries:
        return 0

    week = _week_floor(date.today())
    inserted = 0
    for e in entries:
        try:
            tour = Tour(e.tour.lower())
        except ValueError:
            continue

        player = _upsert_player(session, e, tour)
        if player.id is None:
            continue

        existing = session.exec(
            select(Ranking).where(
                Ranking.player_id == player.id,
                Ranking.tour == tour,
                Ranking.week == week,
            )
        ).first()
        if existing:
            if existing.rank != e.rank or existing.points != e.points:
                existing.rank = e.rank
                existing.points = e.points
                session.add(existing)
        else:
            session.add(
                Ranking(
                    player_id=player.id,
                    tour=tour,
                    week=week,
                    rank=e.rank,
                    points=e.points,
                )
            )
            inserted += 1

        # Snapshot on Player for fast list rendering
        if player.current_rank != e.rank:
            player.current_rank = e.rank
        if player.career_high_rank is None or e.rank < player.career_high_rank:
            player.career_high_rank = e.rank
        # Backfill country if upstream supplies it
        iso3 = name_to_iso3(e.country_name)
        if iso3 and not player.country_code:
            player.country_code = iso3
        player.updated_at = datetime.utcnow()
        session.add(player)

    session.commit()
    return inserted
