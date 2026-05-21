from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select, func

from app.api._helpers import player_summary
from app.db.session import get_session
from app.models.player import Player, Tour
from app.models.ranking import Ranking
from app.schemas.ranking import (
    LiveRankingRow,
    LiveRankingsResponse,
    RankingRow,
    RankingsResponse,
)
from app.services.live_rankings import compute_live_rankings

router = APIRouter(prefix="/api/rankings", tags=["rankings"])


@router.get("/{tour}", response_model=RankingsResponse)
def get_rankings(
    tour: Tour,
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(get_session),
):
    latest_week = session.exec(
        select(func.max(Ranking.week)).where(Ranking.tour == tour)
    ).first()

    if not latest_week:
        return RankingsResponse(tour=tour.value, week="1970-01-01", rows=[])

    stmt = (
        select(Ranking, Player)
        .join(Player, Player.id == Ranking.player_id)
        .where(Ranking.tour == tour, Ranking.week == latest_week)
        .order_by(Ranking.rank)
        .limit(limit)
    )
    rows = session.exec(stmt).all()
    return RankingsResponse(
        tour=tour.value,
        week=latest_week,
        rows=[
            RankingRow(rank=r.rank, points=r.points, player=player_summary(p))
            for r, p in rows
        ],
    )


@router.get("/{tour}/live", response_model=LiveRankingsResponse)
def get_live_rankings(
    tour: Tour,
    limit: int = Query(200, ge=1, le=500),
    session: Session = Depends(get_session),
):
    """Projected rankings: official snapshot + this week's earned − defending.

    Re-sorted by `projected_points`. Per-row deltas show how far each
    player has moved relative to the official rank. See
    `app/services/live_rankings.py` for algorithm details and caveats.
    """
    week, rows = compute_live_rankings(session, tour, limit=limit)
    return LiveRankingsResponse(
        tour=tour.value,
        week=week,
        rows=[
            LiveRankingRow(
                rank=r.rank,
                points=r.points,
                projected_rank=r.projected_rank,
                projected_points=r.projected_points,
                points_change=r.points_change,
                player=player_summary(r.player),
            )
            for r in rows
        ],
    )
