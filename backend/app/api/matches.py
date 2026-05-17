import json
from datetime import datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.api._helpers import match_to_summary
from app.db.session import get_session
from app.models.match import Match, MatchStatus
from app.models.tournament import Tournament, TournamentCategory
from app.schemas.match import MatchDetail, MatchStats, MatchSummary

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


@router.get("/live", response_model=list[MatchSummary])
def live_matches(
    limit: int = Query(100, ge=1, le=200),
    session: Session = Depends(get_session),
):
    # Live + suspended (rain delays) keep their in-progress score
    # visible. We ALSO return finished matches whose scheduled_at is
    # within the last 36 hours — wide enough that for any client
    # timezone, "today's finished matches" is covered. The client
    # narrows that set to its own local-date window so users don't
    # have to dig into brackets to see a match that ended an hour ago.
    finished_cutoff = datetime.utcnow() - timedelta(hours=36)
    stmt = (
        select(Match)
        .where(
            Match.status.in_([MatchStatus.LIVE, MatchStatus.SUSPENDED])
            | (
                (Match.status == MatchStatus.FINISHED)
                & (Match.scheduled_at.is_not(None))
                & (Match.scheduled_at >= finished_cutoff)
            )
        )
        .order_by(Match.scheduled_at.desc())
        .limit(limit)
    )
    return [match_to_summary(session, m) for m in session.exec(stmt).all()]


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
    return MatchDetail(
        **summary.model_dump(),
        started_at=m.started_at,
        finished_at=m.finished_at,
        stats=stats,
    )
