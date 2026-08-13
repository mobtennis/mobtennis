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


def _matches_today(
    session,
    t: Tournament,
    p: Player,
    *,
    round: str | None,
    n: int,
    status: MatchStatus = MatchStatus.SCHEDULED,
) -> None:
    noon = datetime.combine(date.today(), time(12, 0))
    for _ in range(n):
        session.add(
            Match(
                tournament_id=t.id,
                player1_id=p.id,
                player2_id=p.id,
                status=status,
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


def test_null_round_today_falls_back_to_deepest_reached(session, player):
    """When today's matches carry no usable round (api-tennis ships some
    events' final-weekend matches with a NULL round, e.g. Montreal), stage is
    inferred from how far the draw has reached — so it still outranks an event
    genuinely in its opening rounds."""
    late = _tournament(session, "montreal", TournamentCategory.ATP_1000)
    opening = _tournament(session, "cincinnati", TournamentCategory.ATP_1000)

    # Montreal: real early/mid rounds already FINISHED (so they inform "deepest
    # reached" but aren't part of the front of the draw), and today's only
    # unplayed match — the final — has no round label.
    for rnd in ("R128", "R64", "R32", "R16", "QF", "SF"):
        _matches_today(session, late, player, round=rnd, n=1, status=MatchStatus.FINISHED)
    _matches_today(session, late, player, round=None, n=1)  # today's final, unlabelled

    _matches_today(session, opening, player, round="R128", n=44)

    order = _live_order(session)
    assert order.index("Montreal") < order.index("Cincinnati")


def test_tier_still_trumps_stage(session, player):
    """A Grand Slam at its opening round still outranks a 1000 at its final —
    tier is the top-level sort key, ahead of stage depth."""
    slam = _tournament(session, "wimbledon", TournamentCategory.GRAND_SLAM)
    masters = _tournament(session, "canada", TournamentCategory.ATP_1000)

    _matches_today(session, slam, player, round="R128", n=64)
    _matches_today(session, masters, player, round="F", n=1)

    order = _live_order(session)
    assert order.index("Wimbledon") < order.index("Canada")
