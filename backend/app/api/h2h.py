from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api._helpers import match_to_summary, player_summary
from app.db.session import get_session
from app.models.match import Match, MatchStatus
from app.models.player import Player
from app.models.tournament import Tournament
from app.schemas.h2h import H2HResponse, H2HSurfaceSplit

router = APIRouter(prefix="/api/h2h", tags=["h2h"])


@router.get("/{matchup}", response_model=H2HResponse)
def head_to_head(matchup: str, session: Session = Depends(get_session)):
    """matchup is `slug1-vs-slug2`, e.g. `alcaraz-vs-sinner`."""
    if "-vs-" not in matchup:
        raise HTTPException(400, "Use format: slug1-vs-slug2")
    s1, s2 = matchup.split("-vs-", 1)

    p1 = session.exec(select(Player).where(Player.slug.contains(s1))).first()
    p2 = session.exec(select(Player).where(Player.slug.contains(s2))).first()
    if not p1 or not p2:
        raise HTTPException(404, "Player(s) not found")

    stmt = (
        select(Match)
        .where(
            ((Match.player1_id == p1.id) & (Match.player2_id == p2.id))
            | ((Match.player1_id == p2.id) & (Match.player2_id == p1.id)),
            Match.status == MatchStatus.FINISHED,
        )
        .order_by(Match.scheduled_at.desc())
    )
    matches = session.exec(stmt).all()

    p1_wins = sum(1 for m in matches if m.winner_id == p1.id)
    p2_wins = sum(1 for m in matches if m.winner_id == p2.id)

    surface_counts = defaultdict(lambda: [0, 0])
    for m in matches:
        t = session.get(Tournament, m.tournament_id)
        surface = (t.surface if t else None) or "unknown"
        if m.winner_id == p1.id:
            surface_counts[surface][0] += 1
        elif m.winner_id == p2.id:
            surface_counts[surface][1] += 1

    return H2HResponse(
        player1=player_summary(p1),
        player2=player_summary(p2),
        p1_wins=p1_wins,
        p2_wins=p2_wins,
        matches=[match_to_summary(session, m) for m in matches[:20]],
        surface_splits=[
            H2HSurfaceSplit(surface=s, p1_wins=v[0], p2_wins=v[1])
            for s, v in surface_counts.items()
        ],
    )
