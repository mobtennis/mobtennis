"""Tests for /api/matches/* endpoints.

Focus: /upcoming-featured, which drives the "always show big tournaments"
behaviour on the home page. Catching regressions here matters because
this endpoint is consumed by both web and mobile home pages, and any
breakage silently makes the live page look thin.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.match import Match, MatchStatus
from app.models.player import Player, Tour
from app.models.tournament import Tournament, TournamentCategory


@pytest.fixture
def client():
    return TestClient(app)


def _player(session, name: str) -> Player:
    p = Player(slug=name.lower().replace(" ", "-"), full_name=name, tour=Tour.ATP)
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def _tournament(
    session,
    *,
    slug: str,
    category: TournamentCategory,
    tour: Tour = Tour.ATP,
    year: int = 2026,
) -> Tournament:
    t = Tournament(slug=slug, year=year, name=slug.title(), tour=tour, category=category)
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


def _match(
    session,
    *,
    tournament: Tournament,
    p1: Player,
    p2: Player,
    status: MatchStatus = MatchStatus.SCHEDULED,
    scheduled_at: datetime,
) -> Match:
    m = Match(
        tournament_id=tournament.id,
        player1_id=p1.id,
        player2_id=p2.id,
        status=status,
        scheduled_at=scheduled_at,
        round="R32",
    )
    session.add(m)
    session.commit()
    session.refresh(m)
    return m


class TestUpcomingFeatured:
    def test_returns_top_tier_scheduled(self, session, client):
        # Set up: Rome (atp_1000) with one scheduled match in 4h.
        p1 = _player(session, "Jannik Sinner")
        p2 = _player(session, "Carlos Alcaraz")
        t = _tournament(session, slug="rome", category=TournamentCategory.ATP_1000)
        _match(
            session,
            tournament=t,
            p1=p1,
            p2=p2,
            status=MatchStatus.SCHEDULED,
            scheduled_at=datetime.utcnow() + timedelta(hours=4),
        )

        r = client.get("/api/matches/upcoming-featured")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["tournament_slug"] == "rome"
        assert data[0]["player1"]["full_name"] == "Jannik Sinner"

    def test_excludes_low_tier(self, session, client):
        # ITF challenger match: must not show up even when scheduled soon.
        p1 = _player(session, "A Smith")
        p2 = _player(session, "B Jones")
        t = _tournament(session, slug="m25-pula", category=TournamentCategory.ITF)
        _match(
            session,
            tournament=t,
            p1=p1,
            p2=p2,
            scheduled_at=datetime.utcnow() + timedelta(hours=2),
        )

        r = client.get("/api/matches/upcoming-featured")
        assert r.json() == []

    def test_excludes_live_matches(self, session, client):
        # Already-live match: it's covered by /api/matches/live, not here.
        p1 = _player(session, "A One")
        p2 = _player(session, "B Two")
        t = _tournament(session, slug="rome", category=TournamentCategory.ATP_1000)
        _match(
            session,
            tournament=t,
            p1=p1,
            p2=p2,
            status=MatchStatus.LIVE,
            scheduled_at=datetime.utcnow() - timedelta(minutes=30),
        )

        r = client.get("/api/matches/upcoming-featured")
        assert r.json() == []

    def test_excludes_past_scheduled(self, session, client):
        # The 30-min UI-side cutoff is in the frontend; the backend
        # filter is just "in the future". Past-scheduled rows should
        # never appear.
        p1 = _player(session, "C Three")
        p2 = _player(session, "D Four")
        t = _tournament(session, slug="madrid", category=TournamentCategory.ATP_1000)
        _match(
            session,
            tournament=t,
            p1=p1,
            p2=p2,
            scheduled_at=datetime.utcnow() - timedelta(hours=1),
        )

        r = client.get("/api/matches/upcoming-featured")
        assert r.json() == []

    def test_excludes_beyond_horizon(self, session, client):
        # 48h ahead — beyond the 36h horizon, shouldn't appear.
        p1 = _player(session, "E Five")
        p2 = _player(session, "F Six")
        t = _tournament(session, slug="rome", category=TournamentCategory.ATP_1000)
        _match(
            session,
            tournament=t,
            p1=p1,
            p2=p2,
            scheduled_at=datetime.utcnow() + timedelta(hours=48),
        )

        r = client.get("/api/matches/upcoming-featured")
        assert r.json() == []

    def test_sorted_by_scheduled_at(self, session, client):
        # Three big-tournament matches at different times — must come
        # back soonest-first so the client can take "next N per tournament".
        t = _tournament(session, slug="rome", category=TournamentCategory.ATP_1000)
        a, b, c, d, e, f = [_player(session, f"P{i}") for i in range(6)]
        _match(
            session,
            tournament=t,
            p1=a,
            p2=b,
            scheduled_at=datetime.utcnow() + timedelta(hours=10),
        )
        _match(
            session,
            tournament=t,
            p1=c,
            p2=d,
            scheduled_at=datetime.utcnow() + timedelta(hours=2),
        )
        _match(
            session,
            tournament=t,
            p1=e,
            p2=f,
            scheduled_at=datetime.utcnow() + timedelta(hours=6),
        )

        r = client.get("/api/matches/upcoming-featured")
        names = [m["player1"]["full_name"] for m in r.json()]
        assert names == ["P2", "P4", "P0"]

    def test_includes_wta_1000_and_grand_slam(self, session, client):
        # Coverage of the full FEATURED_CATEGORIES set.
        p1 = _player(session, "A One")
        p2 = _player(session, "B Two")
        p3 = _player(session, "C Three")
        p4 = _player(session, "D Four")
        wta = _tournament(
            session, slug="madrid-wta",
            category=TournamentCategory.WTA_1000, tour=Tour.WTA,
        )
        slam = _tournament(session, slug="french-open", category=TournamentCategory.GRAND_SLAM)
        _match(
            session, tournament=wta, p1=p1, p2=p2,
            scheduled_at=datetime.utcnow() + timedelta(hours=3),
        )
        _match(
            session, tournament=slam, p1=p3, p2=p4,
            scheduled_at=datetime.utcnow() + timedelta(hours=5),
        )

        r = client.get("/api/matches/upcoming-featured")
        slugs = {m["tournament_slug"] for m in r.json()}
        assert slugs == {"madrid-wta", "french-open"}
