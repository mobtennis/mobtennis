from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db.session import get_session
from app.models.player import Player
from app.models.tournament import Tournament

router = APIRouter(prefix="/api/search", tags=["search"])


class SearchHit(BaseModel):
    kind: str  # "player" | "tournament"
    slug: str
    name: str
    tour: str | None = None
    year: int | None = None
    country_code: str | None = None
    rank: int | None = None


@router.get("", response_model=list[SearchHit])
def search(
    q: str = Query(..., min_length=1),
    limit: int = Query(15, ge=1, le=50),
    session: Session = Depends(get_session),
):
    pattern = f"%{q}%"
    players = session.exec(
        select(Player)
        .where(Player.full_name.ilike(pattern))
        .order_by(Player.current_rank.is_(None), Player.current_rank)
        .limit(limit)
    ).all()
    tournaments = session.exec(
        select(Tournament)
        .where(Tournament.name.ilike(pattern))
        .order_by(Tournament.year.desc())
        .limit(limit)
    ).all()

    hits = [
        SearchHit(
            kind="player", slug=p.slug, name=p.full_name, tour=p.tour.value,
            country_code=p.country_code, rank=p.current_rank,
        )
        for p in players
    ] + [
        SearchHit(kind="tournament", slug=t.slug, name=t.name, tour=t.tour.value, year=t.year)
        for t in tournaments
    ]
    return hits[:limit]
