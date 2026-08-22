import json
import threading
import time
from collections.abc import Callable
from typing import TypeVar

from sqlalchemy import or_
from sqlmodel import Session, select

_T = TypeVar("_T")


def single_flight(
    store: dict,
    key,
    ttl: float,
    lock: threading.Lock,
    compute: Callable[[], _T],
) -> _T:
    """Return a cached value or compute it once under a lock (thundering-herd
    protection). Endpoints are sync `def` handlers run in Starlette's
    threadpool, so a threading.Lock is the right primitive: on cache expiry
    the first thread computes while the rest block briefly and then read the
    fresh value — instead of N concurrent recomputes of the same expensive
    query (the stampede that caused 10–17s latency cliffs under load).

    `store` holds {key: (monotonic_ts, value)}.
    """
    hit = store.get(key)
    if hit and (time.monotonic() - hit[0]) < ttl:
        return hit[1]
    with lock:
        hit = store.get(key)  # re-check — another thread may have filled it
        if hit and (time.monotonic() - hit[0]) < ttl:
            return hit[1]
        value = compute()
        store[key] = (time.monotonic(), value)
        return value

from app.models.match import Match, MatchStatus
from app.models.player import Player
from app.models.tournament import Tournament
from app.schemas.match import MatchSummary
from app.schemas.player import PlayerSummary


def _momentum_spark(momentum_json: str | None, n: int = 16) -> list[int] | None:
    """Downsample a stored momentum series to a tiny sparkline for listing
    cards — a teaser that hints the full wave is on the match page.

    Returns ~n evenly-spaced momentum values (−100..100, player1-oriented) or
    None. Cheap: most matches have no momentum_json (skipped); the ones that
    do parse a small blob. We never ship the full series to list endpoints.
    """
    if not momentum_json:
        return None
    try:
        series = (json.loads(momentum_json) or {}).get("series") or []
    except (ValueError, TypeError):
        return None
    ms = [round(pt.get("m", 0)) for pt in series if isinstance(pt, dict)]
    if len(ms) < 4:
        return None
    if len(ms) <= n:
        return ms
    step = (len(ms) - 1) / (n - 1)
    return [ms[round(i * step)] for i in range(n)]


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
        duration_minutes=m.duration_minutes,
        api_tennis_id=m.api_tennis_id,
        bracket_position=m.bracket_position,
        player1_seed=m.player1_seed,
        player2_seed=m.player2_seed,
        momentum_spark=_momentum_spark(m.momentum_json),
    )


def exclude_junior_rounds(stmt):
    """Skip junior-bracket matches at Slams.

    At Slams the junior brackets share the same Tournament row as the
    main draw, but their match labels come through in two shapes:

      1. Verbose with the gender prefix: "Boys French Open -
         Semi-finals", "Girls French Open - 1/32-finals", etc. Easy
         to filter by `startswith("Boys ")` / `startswith("Girls ")`.

      2. NULL round label for junior DOUBLES. Main-draw Slam doubles
         always lands with an "ATP French Open - 1/8-finals" or
         "French Open - Quarter-finals" (mixed) round label, so a
         null round at a Slam means we couldn't classify the match —
         in practice always a junior doubles bracket.

    Joins on Tournament.category to scope the null-round filter to
    grand_slam tournaments only — ITF/Challenger matches legitimately
    have null rounds (early-round labels are often missing from
    api-tennis) and we want those on the live page.

    The caller must already have the Tournament join in place; both
    /live and /upcoming-featured join Tournament for tier_priority.
    /today does not — its stmt builder calls join_tournament_if_needed
    via the second argument flag.
    """
    from app.models.tournament import Tournament, TournamentCategory
    return stmt.where(
        # Prefix exclusion (verbose junior singles + doubles labels).
        Match.round.is_(None)
        | ~or_(
            Match.round.startswith("Boys "),
            Match.round.startswith("Girls "),
        )
    ).where(
        # Null-round-at-Slam exclusion: drop, everywhere else keep.
        ~(
            (Tournament.category == TournamentCategory.GRAND_SLAM)
            & Match.round.is_(None)
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
