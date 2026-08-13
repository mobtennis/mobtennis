"""Tests for the tournaments-index "Happening now" ordering.

The live section used to sort purely on match volume within a tier. Because
a draw has the MOST matches at its start (round of 128) and the FEWEST at its
final, that floated opening-round events above events reaching their climax —
e.g. Cincinnati's round-of-128 (44 matches today) outranking the Toronto /
Montreal finals. Ordering now prefers how far along the event is (stage depth)
over raw volume. See `_compute_index_sections`.
"""

from __future__ import annotations

from datetime import date, datetime, time

import pytest

from app.api.tournaments import _compute_index_sections
from app.models.match import Match, MatchStatus
from app.models.player import Player, Tour
from app.models.tournament import Tournament, TournamentCategory


@pytest.fixture
def player(session) -> Player:
    p = Player(slug="p", full_name="P", tour=Tour.ATP)
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def _tournament(session, slug: str, category: TournamentCategory) -> Tournament:
    t = Tournament(slug=slug, year=2026, name=slug.title(), tour=Tour.ATP, category=category)
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


def _matches_today(session, t: Tournament, p: Player, *, round: str, n: int) -> None:
    noon = datetime.combine(date.today(), time(12, 0))
    for _ in range(n):
        session.add(
            Match(
                tournament_id=t.id,
                player1_id=p.id,
                player2_id=p.id,
                status=MatchStatus.SCHEDULED,
                scheduled_at=noon,
                round=round,
            )
        )
    session.commit()


def _live_order(session) -> list[str]:
    for key, _title, items in _compute_index_sections(session):
        if key == "live":
            return [i.name for i in items]
    return []


def test_final_stage_outranks_opening_rounds_despite_volume(session, player):
    """A same-tier event at its final beats one in its opening rounds, even
    though the opening-round event has far more matches on today's schedule."""
    final = _tournament(session, "canada", TournamentCategory.ATP_1000)
    opening = _tournament(session, "cincinnati", TournamentCategory.ATP_1000)

    _matches_today(session, final, player, round="F", n=1)
    _matches_today(session, opening, player, round="R128", n=44)

    order = _live_order(session)
    assert order.index("Canada") < order.index("Cincinnati")


def test_tier_still_trumps_stage(session, player):
    """A Grand Slam at its opening round still outranks a 1000 at its final —
    tier is the top-level sort key, ahead of stage depth."""
    slam = _tournament(session, "wimbledon", TournamentCategory.GRAND_SLAM)
    masters = _tournament(session, "canada", TournamentCategory.ATP_1000)

    _matches_today(session, slam, player, round="R128", n=64)
    _matches_today(session, masters, player, round="F", n=1)

    order = _live_order(session)
    assert order.index("Wimbledon") < order.index("Canada")
