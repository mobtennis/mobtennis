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
    # Both slugs must be non-empty. Previously a malformed URL like
    # `/api/h2h/alcaraz-vs-` produced s2="" and Player.slug.contains("")
    # matched the first player row in the table → wrong player + an
    # expensive scan. Crawlers hitting variations on this pattern were
    # the cause of an event-loop pileup that ground the box to a halt.
    if not s1 or not s2:
        raise HTTPException(400, "Use format: slug1-vs-slug2 (both required)")

    # Exact slug match. We use canonical slugs everywhere; `.contains()`
    # was over-permissive and let stray fragments resolve to arbitrary
    # players.
    p1 = session.exec(select(Player).where(Player.slug == s1)).first()
    p2 = session.exec(select(Player).where(Player.slug == s2)).first()
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

    # Eager-load tournaments referenced by these matches in ONE query
    # instead of one-per-match (was N+1: 100+ extra queries for a
    # long-running rivalry). Build a map from id → surface.
    tournament_ids = {m.tournament_id for m in matches if m.tournament_id}
    surface_by_tid: dict[int, str] = {}
    if tournament_ids:
        for tid, surface in session.exec(
            select(Tournament.id, Tournament.surface).where(Tournament.id.in_(tournament_ids))
        ).all():
            surface_by_tid[tid] = surface or "unknown"

    surface_counts = defaultdict(lambda: [0, 0])
    for m in matches:
        surface = surface_by_tid.get(m.tournament_id, "unknown")
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
