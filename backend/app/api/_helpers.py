from sqlalchemy import or_
from sqlmodel import Session, select

from app.models.match import Match, MatchStatus
from app.models.player import Player
from app.models.tournament import Tournament
from app.schemas.match import MatchSummary
from app.schemas.player import PlayerSummary


def player_summary(p: Player | None) -> PlayerSummary | None:
    if not p:
        return None
    return PlayerSummary(
        slug=p.slug,
        full_name=p.full_name,
        tour=p.tour,
        country_code=p.country_code,
        current_rank=p.current_rank,
        image_url=p.image_url,
    )


def match_to_summary(session: Session, m: Match) -> MatchSummary:
    t = session.get(Tournament, m.tournament_id)
    p1 = session.get(Player, m.player1_id) if m.player1_id else None
    p2 = session.get(Player, m.player2_id) if m.player2_id else None

    def to_slot(target_id: int | None) -> int | None:
        """Map a player FK back to its 1/2 slot in this match."""
        if target_id is None:
            return None
        if p1 and target_id == p1.id:
            return 1
        if p2 and target_id == p2.id:
            return 2
        return None

    return MatchSummary(
        id=m.id,
        tournament_slug=t.slug if t else "",
        tournament_year=t.year if t else 0,
        tournament_name=t.name if t else "",
        tournament_tour=t.tour.value if t and t.tour else None,
        tournament_category=t.category.value if t and t.category else None,
        tournament_surface=t.surface if t else None,
        round=m.round,
        court=m.court,
        scheduled_at=m.scheduled_at,
        status=m.status,
        player1=player_summary(p1),
        player2=player_summary(p2),
        score=m.score,
        current_set=m.current_set,
        current_game=m.current_game,
        server_player_id=m.server_player_id,
        server_slot=to_slot(m.server_player_id),
        winner_id=m.winner_id,
        winner_slot=to_slot(m.winner_id),
        is_doubles=m.is_doubles,
        best_of=m.best_of,
        api_tennis_id=m.api_tennis_id,
        bracket_position=m.bracket_position,
        player1_seed=m.player1_seed,
        player2_seed=m.player2_seed,
    )


def exclude_junior_rounds(stmt):
    """Skip Boys'/Girls' brackets at Slams (junior tour).

    At Slams the junior brackets share the same Tournament row as the
    main draw but use verbose round labels prefixed "Boys " / "Girls "
    (e.g. "Boys French Open - Semi-finals"), whereas main-draw rounds
    use short codes like "F", "SF", "QF". Filter on the prefix and
    keep NULL rounds (lower-tier ITF/Challenger matches in our DB
    often have null round labels).
    """
    return stmt.where(
        Match.round.is_(None)
        | ~or_(
            Match.round.startswith("Boys "),
            Match.round.startswith("Girls "),
        )
    )


def filter_status(stmt, status: str | None):
    if status == "live":
        return stmt.where(Match.status == MatchStatus.LIVE)
    if status == "scheduled":
        return stmt.where(Match.status == MatchStatus.SCHEDULED)
    if status == "finished":
        return stmt.where(Match.status == MatchStatus.FINISHED)
    return stmt
