from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api._helpers import match_to_summary, player_summary
from app.db.session import get_session
from app.models.match import Match, MatchStatus
from app.models.player import Player
from app.models.tournament import Tournament
from app.schemas.h2h import H2HMeeting, H2HResponse, H2HSummary, H2HSurfaceSplit

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
    # long-running rivalry). Build maps id → (surface, name, slug, tour).
    tournament_ids = {m.tournament_id for m in matches if m.tournament_id}
    surface_by_tid: dict[int, str] = {}
    tournament_meta: dict[int, tuple[str | None, str | None, str | None]] = {}
    if tournament_ids:
        for tid, surface, name, slug, tour in session.exec(
            select(
                Tournament.id, Tournament.surface, Tournament.name,
                Tournament.slug, Tournament.tour,
            ).where(Tournament.id.in_(tournament_ids))
        ).all():
            surface_by_tid[tid] = surface or "unknown"
            tournament_meta[tid] = (
                name,
                slug,
                tour.value if hasattr(tour, "value") else (tour if isinstance(tour, str) else None),
            )

    surface_counts = defaultdict(lambda: [0, 0])
    for m in matches:
        surface = surface_by_tid.get(m.tournament_id, "unknown")
        if m.winner_id == p1.id:
            surface_counts[surface][0] += 1
        elif m.winner_id == p2.id:
            surface_counts[surface][1] += 1

    summary = _build_summary(matches, p1, p2, tournament_meta)

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
        summary=summary,
    )


def _build_summary(
    matches: list[Match],
    p1: Player,
    p2: Player,
    tournament_meta: dict[int, tuple[str | None, str | None, str | None]],
) -> H2HSummary | None:
    """Compute the H2H summary block from the full match list.

    Matches arrive in scheduled_at DESC order from the caller. We use
    that ordering throughout — head = most recent, last = oldest.
    """
    if not matches:
        return H2HSummary(
            total_meetings=0,
            finals_meetings=0,
            span_years=None,
            first_meeting=None,
            last_meeting=None,
            current_streak_slug=None,
            current_streak_count=0,
        )

    def _to_meeting(m: Match) -> H2HMeeting | None:
        if m.scheduled_at is None:
            return None
        meta = tournament_meta.get(m.tournament_id)
        name, slug, tour = (meta if meta is not None else (None, None, None))
        winner_slug = (
            p1.slug if m.winner_id == p1.id
            else p2.slug if m.winner_id == p2.id
            else None
        )
        return H2HMeeting(
            year=m.scheduled_at.year,
            tournament_name=name,
            tournament_slug=slug,
            tournament_tour=tour,
            round=m.round,
            winner_slug=winner_slug,
            score=m.score,
        )

    last_meeting = _to_meeting(matches[0])
    first_meeting = _to_meeting(matches[-1])
    span = None
    if last_meeting and first_meeting and last_meeting.year != first_meeting.year:
        span = last_meeting.year - first_meeting.year

    # Main-draw final count = ONLY the short code "F" from Sackmann +
    # Wikipedia. We deliberately do NOT match verbose api-tennis labels
    # like "ATP French Open - Final" because those also tag the
    # qualifying-bracket final, and counting two players' qualifying-
    # bracket meeting as "they met in a Slam Final" is absurd. See
    # api/players.py snapshot logic for the longer explanation.
    finals_meetings = sum(1 for m in matches if m.round == "F")

    # Current streak: walk from most recent until the winner changes.
    streak_slug: str | None = None
    streak_count = 0
    for m in matches:
        winner = (
            p1.slug if m.winner_id == p1.id
            else p2.slug if m.winner_id == p2.id
            else None
        )
        if winner is None:
            break
        if streak_slug is None:
            streak_slug = winner
            streak_count = 1
        elif winner == streak_slug:
            streak_count += 1
        else:
            break

    return H2HSummary(
        total_meetings=len(matches),
        finals_meetings=finals_meetings,
        span_years=span,
        first_meeting=first_meeting,
        last_meeting=last_meeting,
        current_streak_slug=streak_slug,
        current_streak_count=streak_count,
    )
