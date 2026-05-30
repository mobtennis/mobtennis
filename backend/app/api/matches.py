import json
from datetime import datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case
from sqlmodel import Session, select

from app.api._helpers import match_to_summary
from app.db.session import get_session
from app.models.match import Match, MatchStatus
from app.models.player import Player
from app.models.tournament import Tournament, TournamentCategory
from app.schemas.match import MatchBlurb, MatchDetail, MatchStats, MatchSummary
from app.services.match_blurb import build_blurb, compute_h2h_context

router = APIRouter(prefix="/api/matches", tags=["matches"])


# Tournaments we always want to surface on the home page, even between
# match sessions or on rest days. Top-tier brand events where users
# expect a permanent presence on the live page during the tournament.
FEATURED_CATEGORIES = (
    TournamentCategory.GRAND_SLAM,
    TournamentCategory.ATP_1000,
    TournamentCategory.WTA_1000,
    TournamentCategory.ATP_FINALS,
    TournamentCategory.WTA_FINALS,
)

# Look ahead this far when picking "next up" matches. 36h catches early-
# morning fixtures (and the second-day session of a finals weekend) without
# bleeding into matches several days out.
FEATURED_HORIZON = timedelta(hours=36)


# Small in-process cache for /live. The frontend ISR layer used to
# carry the load-protection role (revalidate: 15 on the fetch), but
# that defeated SSE-triggered refreshes because router.refresh() hit
# the cache and got stale data back. Cache moved server-side so the
# frontend can pass `cache: 'no-store'` and get fresh-ish data on
# every request, while N concurrent visitors during a busy Slam day
# don't multiply into N concurrent SQL queries.
import time as _time
_LIVE_CACHE: dict[tuple[int], tuple[float, list]] = {}
_LIVE_CACHE_TTL = 5.0  # seconds


@router.get("/live", response_model=list[MatchSummary])
def live_matches(
    limit: int = Query(100, ge=1, le=200),
    session: Session = Depends(get_session),
):
    # 5-second in-process cache. Burst of clicks during a tense game
    # all hit the same cached payload; outside the burst, every
    # request hits the SQL. The TTL is short enough that "30 seconds
    # behind reality" isn't a thing the user can notice.
    cache_key = (limit,)
    hit = _LIVE_CACHE.get(cache_key)
    if hit and (_time.monotonic() - hit[0]) < _LIVE_CACHE_TTL:
        return hit[1]

    # Live + suspended (rain delays) keep their in-progress score
    # visible. We ALSO return finished matches whose scheduled_at is
    # within the last 36 hours — wide enough that for any client
    # timezone, "today's finished matches" is covered. The client
    # narrows that set to its own local-date window so users don't
    # have to dig into brackets to see a match that ended an hour ago.
    #
    # Sort priority (descending importance):
    #   1. LIVE / SUSPENDED outrank FINISHED. An in-progress 250 match
    #      still beats a finished Slam from this morning.
    #   2. Tournament tier (Slam > 1000 > 500 > 250 > Davis > Challenger
    #      > ITF). The original chronological-only sort buried French
    #      Open day-1 matches behind Challengers scheduled 10 minutes
    #      later, because the LIMIT was hit before slams appeared.
    #   3. scheduled_at desc — within a tier, most recent first.
    finished_cutoff = datetime.utcnow() - timedelta(hours=36)
    status_priority = case(
        (Match.status == MatchStatus.LIVE, 0),
        (Match.status == MatchStatus.SUSPENDED, 1),
        else_=2,
    )
    tier_priority = case(
        (Tournament.category == TournamentCategory.GRAND_SLAM, 0),
        (Tournament.category == TournamentCategory.ATP_FINALS, 1),
        (Tournament.category == TournamentCategory.WTA_FINALS, 1),
        (Tournament.category == TournamentCategory.ATP_1000, 2),
        (Tournament.category == TournamentCategory.WTA_1000, 2),
        (Tournament.category == TournamentCategory.ATP_500, 3),
        (Tournament.category == TournamentCategory.WTA_500, 3),
        (Tournament.category == TournamentCategory.ATP_250, 4),
        (Tournament.category == TournamentCategory.WTA_250, 4),
        (Tournament.category == TournamentCategory.DAVIS_CUP, 5),
        (Tournament.category == TournamentCategory.BJK_CUP, 5),
        (Tournament.category == TournamentCategory.CHALLENGER, 6),
        (Tournament.category == TournamentCategory.ITF, 7),
        else_=8,
    )
    stmt = (
        select(Match)
        .join(Tournament, Tournament.id == Match.tournament_id)
        .where(
            Match.status.in_([MatchStatus.LIVE, MatchStatus.SUSPENDED])
            | (
                (Match.status == MatchStatus.FINISHED)
                & (Match.scheduled_at.is_not(None))
                & (Match.scheduled_at >= finished_cutoff)
            )
        )
        .order_by(status_priority, tier_priority, Match.scheduled_at.desc())
        .limit(limit)
    )
    out = [match_to_summary(session, m) for m in session.exec(stmt).all()]
    _LIVE_CACHE[cache_key] = (_time.monotonic(), out)
    return out


@router.get("/today", response_model=list[MatchSummary])
def today_matches(
    limit: int = Query(200, ge=1, le=500),
    session: Session = Depends(get_session),
):
    today_start = datetime.combine(datetime.utcnow().date(), time.min)
    today_end = datetime.combine(datetime.utcnow().date(), time.max)
    stmt = (
        select(Match)
        .where(Match.scheduled_at >= today_start, Match.scheduled_at <= today_end)
        .order_by(Match.scheduled_at)
        .limit(limit)
    )
    return [match_to_summary(session, m) for m in session.exec(stmt).all()]


@router.get("/upcoming-featured", response_model=list[MatchSummary])
def upcoming_featured_matches(
    limit: int = Query(60, ge=1, le=200),
    session: Session = Depends(get_session),
):
    """Scheduled matches in the next ~36 hours for top-tier tournaments.

    Used by the home page to surface "next up" entries for Grand Slams and
    ATP/WTA 1000s, even when no match in that tournament is currently
    playing (e.g. between morning and evening sessions, or on a finals-day
    morning before the match starts).

    Ordered by scheduled_at ascending so a client taking the first N per
    tournament gets the most imminent matches.
    """
    now = datetime.utcnow()
    horizon = now + FEATURED_HORIZON
    stmt = (
        select(Match)
        .join(Tournament, Tournament.id == Match.tournament_id)
        .where(Match.status == MatchStatus.SCHEDULED)
        .where(Match.scheduled_at.is_not(None))
        .where(Match.scheduled_at >= now)
        .where(Match.scheduled_at <= horizon)
        .where(Tournament.category.in_(FEATURED_CATEGORIES))
        .order_by(Match.scheduled_at)
        .limit(limit)
    )
    return [match_to_summary(session, m) for m in session.exec(stmt).all()]


@router.get("/{match_id}", response_model=MatchDetail)
def get_match(match_id: int, session: Session = Depends(get_session)):
    m = session.get(Match, match_id)
    if not m:
        raise HTTPException(404, "Match not found")
    summary = match_to_summary(session, m)
    stats: MatchStats | None = None
    if m.stats_json:
        try:
            stats = MatchStats.model_validate(json.loads(m.stats_json))
        except (ValueError, TypeError):
            stats = None

    # Templated editorial blurb. Only doubles are skipped — H2H data for
    # doubles pairings is too sparse for the templates to say anything
    # meaningful, and the page already has the score + stats up top.
    blurb: MatchBlurb | None = None
    if not m.is_doubles and m.player1_id and m.player2_id:
        p1 = session.get(Player, m.player1_id)
        p2 = session.get(Player, m.player2_id)
        tournament = session.get(Tournament, m.tournament_id) if m.tournament_id else None
        if p1 and p2 and tournament:
            h2h_ctx = compute_h2h_context(session, m, p1, p2)
            kind, paragraph = build_blurb(m, p1, p2, tournament, h2h_ctx)
            if kind and paragraph:
                blurb = MatchBlurb(kind=kind, paragraph=paragraph)

    return MatchDetail(
        **summary.model_dump(),
        started_at=m.started_at,
        finished_at=m.finished_at,
        stats=stats,
        blurb=blurb,
    )
