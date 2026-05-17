import asyncio
from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, or_, select

from app.api._helpers import match_to_summary
from app.db.session import get_session
from app.models.match import Match, MatchStatus
from app.models.player import Player, Tour
from app.models.ranking import Ranking
from app.models.tournament import Tournament
from app.schemas.history import TournamentHistoryEntry
from app.schemas.match import MatchSummary
from app.schemas.player import PlayerDetail, PlayerSummary
from app.services.player_enrich import enrich_one
from app.services.rounds import compute_player_result, round_depth

router = APIRouter(prefix="/api/players", tags=["players"])


@router.get("", response_model=list[PlayerSummary])
def list_players(
    tour: Tour | None = None,
    q: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    stmt = select(Player)
    if tour:
        stmt = stmt.where(Player.tour == tour)
    if q:
        stmt = stmt.where(Player.full_name.ilike(f"%{q}%"))
    stmt = stmt.order_by(Player.current_rank.is_(None), Player.current_rank).limit(limit)
    rows = session.exec(stmt).all()
    return [
        PlayerSummary(
            slug=p.slug, full_name=p.full_name, tour=p.tour,
            country_code=p.country_code, current_rank=p.current_rank, image_url=p.image_url,
        )
        for p in rows
    ]


@router.get("/{slug}", response_model=PlayerDetail)
async def get_player(slug: str, session: Session = Depends(get_session)):
    p = session.exec(select(Player).where(Player.slug == slug)).first()
    if not p:
        raise HTTPException(404, "Player not found")

    # Lazy enrichment: first visit to a player page triggers a get_players call
    # to fetch image / country / birth_date. Capped to 2s so we don't slow the
    # response if the upstream is sluggish; the data lands for the next visit.
    if p.image_url is None and p.api_tennis_id:
        try:
            await asyncio.wait_for(enrich_one(session, p), timeout=2.0)
        except asyncio.TimeoutError:
            pass
        # Re-read in case enrichment committed updates
        session.refresh(p)

    return PlayerDetail(
        slug=p.slug, full_name=p.full_name, tour=p.tour,
        country_code=p.country_code, current_rank=p.current_rank,
        image_url=(p.image_url or None),  # collapse "" → None for the JSON shape
        first_name=p.first_name, last_name=p.last_name, birth_date=p.birth_date,
        height_cm=p.height_cm, plays=p.plays, turned_pro=p.turned_pro,
        career_high_rank=p.career_high_rank, bio=p.bio,
        wikipedia_url=p.wikipedia_url,
        instagram_handle=p.instagram_handle,
        twitter_handle=p.twitter_handle,
        instagram_latest_post_url=p.instagram_latest_post_url,
    )


@router.get("/{slug}/matches", response_model=list[MatchSummary])
def player_matches(
    slug: str,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    p = session.exec(select(Player).where(Player.slug == slug)).first()
    if not p:
        raise HTTPException(404, "Player not found")
    stmt = select(Match).where((Match.player1_id == p.id) | (Match.player2_id == p.id))
    if status:
        from app.api._helpers import filter_status
        stmt = filter_status(stmt, status)
    rows = session.exec(stmt.order_by(Match.scheduled_at.desc()).limit(limit * 4)).all()
    # Within a tournament all matches share scheduled_at (Sackmann pins it
    # to the tournament start), so SQL tie-break is undefined. Re-sort in
    # Python by (scheduled_at, round_depth) descending so the deepest round
    # — the player's most recent match — sits at the top of each group.
    from datetime import datetime as _dt

    from app.services.rounds import round_depth

    rows.sort(
        key=lambda m: (m.scheduled_at or _dt.min, round_depth(m.round)),
        reverse=True,
    )
    return [match_to_summary(session, m) for m in rows[:limit]]


@router.get("/{slug}/rankings")
def player_ranking_history(
    slug: str,
    limit: int = Query(260, ge=1, le=1040),  # 5 years of weeks default
    session: Session = Depends(get_session),
):
    p = session.exec(select(Player).where(Player.slug == slug)).first()
    if not p:
        raise HTTPException(404, "Player not found")
    rows = session.exec(
        select(Ranking).where(Ranking.player_id == p.id).order_by(Ranking.week.desc()).limit(limit)
    ).all()
    return [{"week": r.week, "rank": r.rank, "points": r.points} for r in rows]


@router.get("/{slug}/tournament-history", response_model=list[TournamentHistoryEntry])
def player_tournament_history(
    slug: str,
    limit: int = Query(5, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    """For each tournament the player has participated in, return how far
    they got: W (won the title), F (lost the final), SF, QF, R16, etc.
    Ordered by tournament date, most recent first.
    """
    p = session.exec(select(Player).where(Player.slug == slug)).first()
    if not p:
        raise HTTPException(404, "Player not found")

    rows = session.exec(
        select(Match, Tournament)
        .join(Tournament, Tournament.id == Match.tournament_id)
        .where(or_(Match.player1_id == p.id, Match.player2_id == p.id))
        .where(Match.status == MatchStatus.FINISHED)
    ).all()

    # Group matches by tournament instance (tournament rows are per-year, so
    # this naturally separates Wimbledon 2024 from Wimbledon 2025).
    by_tournament: dict[int, list[tuple[Match, Tournament]]] = defaultdict(list)
    for m, t in rows:
        by_tournament[t.id].append((m, t))

    entries: list[TournamentHistoryEntry] = []
    for _, group in by_tournament.items():
        t = group[0][1]
        deepest_match = max(group, key=lambda mt: round_depth(mt[0].round))[0]
        won_deepest = deepest_match.winner_id == p.id
        result = compute_player_result(deepest_match.round, won_deepest)
        entries.append(
            TournamentHistoryEntry(
                tournament_slug=t.slug,
                tournament_year=t.year,
                tournament_name=t.name,
                tournament_tour=t.tour.value,
                tournament_category=t.category.value if t.category else None,
                tournament_surface=t.surface,
                tournament_image_url=t.image_url,
                start_date=t.start_date,
                end_date=t.end_date,
                result=result,
                is_winner=result == "W",
            )
        )

    # Most recent first. Use end_date when present, else start_date, else year.
    def _sort_key(e: TournamentHistoryEntry) -> tuple[int, date]:
        d = e.end_date or e.start_date or date(e.tournament_year, 1, 1)
        return (e.tournament_year, d)

    entries.sort(key=_sort_key, reverse=True)
    return entries[offset : offset + limit]
