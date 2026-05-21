"""Live ranking projection.

For each player in the latest ranking snapshot:
    projected_points = current_points
                     + earned_this_week (round reached at any tournament
                       running this week, scored by tier)
                     - defending_this_week (round they reached at the
                       same tournament one year ago, dropping off the
                       52-week window as this year's edition completes)

Then resort by projected_points and emit (projected_rank, points_change).

Caveats:
  - "Same tournament last year" uses the canonical brand slug post-merge,
    so the Sackmann/api-tennis name divergence is already reconciled
    (see services/tournament_resolver.py).
  - The defending lookup only includes tournaments running this week. A
    player who played last year's Hamburg but skipped this year's won't
    have those points subtracted here — that's a 52-week-ledger concern
    that v1 deliberately skips (mostly affects players outside the top 30).
  - "Best 18/19" rule is not applied — same as LiveTennis.eu's projection.
  - Players still in the draw earn a MINIMUM lock-in (round-they've-won-
    through) rather than a projection of how far they might go.

Cached in-process for 60s to keep the per-request cost flat when the
homepage and the rankings page both fan out to /api/rankings/{tour}/live.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time as dtime, timedelta

from sqlmodel import Session, func, select

from app.models.match import Match, MatchStatus
from app.models.player import Player, Tour
from app.models.ranking import Ranking
from app.models.tournament import Tournament
from app.services.ranking_points import available_for_round, points_for_result
from app.services.rounds import compute_player_result, round_abbrev, round_depth

log = logging.getLogger(__name__)

# In-process cache. The keys are (tour, limit, current_monday).
_CACHE: dict[tuple[str, int, date], tuple[float, list]] = {}
_CACHE_TTL_S = 60.0


@dataclass
class LiveRow:
    rank: int                 # official rank
    points: int | None        # official points
    projected_rank: int       # rank after this week's net change
    projected_points: int     # current + earned - defending
    points_change: int        # earned - defending (signed)
    player_id: int
    player: Player            # full ORM row for the API helper to serialise


def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def compute_live_rankings(
    session: Session, tour: Tour, *, limit: int = 200,
) -> tuple[date, list[LiveRow]]:
    """Returns (snapshot_week, rows). Rows are sorted by projected_rank."""
    today = date.today()
    cache_key = (tour.value, limit, monday_of(today))
    hit = _CACHE.get(cache_key)
    if hit and (time.monotonic() - hit[0]) < _CACHE_TTL_S:
        return hit[1]

    latest_week = session.exec(
        select(func.max(Ranking.week)).where(Ranking.tour == tour)
    ).first()
    if not latest_week:
        return today, []

    # Pull the snapshot rows + their Player rows in one go.
    ranking_rows = session.exec(
        select(Ranking, Player)
        .join(Player, Player.id == Ranking.player_id)
        .where(Ranking.tour == tour, Ranking.week == latest_week)
        .order_by(Ranking.rank)
        .limit(limit)
    ).all()
    if not ranking_rows:
        return latest_week, []

    player_ids = [r.player_id for r, _ in ranking_rows]
    player_id_set = set(player_ids)

    # "Running" tournament = main draw has begun (≥ 1 main-draw match
    # already scheduled at or before today). We deliberately don't
    # include tournaments where only qualifying has started — qualifying
    # matches don't move ranking points, and triggering "defending"
    # against last year's edition while this year hasn't earned anything
    # produces phantom big losses for the prior year's deep runs.
    #
    # Slams are 2 weeks long, so a player who lost in week 1 still
    # counts as "having played" — we walk all their matches at the
    # tournament regardless of which week they're in.
    this_monday = monday_of(today)
    this_sunday = this_monday + timedelta(days=6)
    today_dt = datetime.combine(today, dtime.max)

    # Round filter: main draw only (R128 or deeper = depth ≥ 40).
    _MAIN_DRAW = ("R128", "R64", "R32", "R16", "QF", "SF", "F",
                  "first round", "second round", "third round",
                  "fourth round",
                  "1/64-finals", "1/32-finals", "1/16-finals",
                  "1/8-finals", "quarter-finals", "semi-finals", "final")
    # `end_date` is NULL on most rows (catalog enrichment is patchy),
    # so we can't rely on a [start, end] containment check. Use a
    # "started within the past 14 days" window instead — wide enough
    # to cover both weeks of a 2-week Slam, tight enough to exclude
    # finished events earlier in the season.
    window_start = this_monday - timedelta(days=14)
    current_tournaments = session.exec(
        select(Tournament)
        .join(Match, Match.tournament_id == Tournament.id)
        .where(
            Match.scheduled_at <= today_dt,
            Match.is_doubles == False,  # noqa: E712
            Tournament.tour == tour,
            Tournament.start_date.is_not(None),
            Tournament.start_date >= window_start,
            Tournament.start_date <= this_sunday,
        )
        .distinct()
    ).all()
    # Drop tournaments where only qualifying has happened so far.
    def _has_main_draw_played(tid: int) -> bool:
        return session.exec(
            select(func.count(Match.id)).where(
                Match.tournament_id == tid,
                Match.scheduled_at <= today_dt,
                Match.round.in_(_MAIN_DRAW),
                Match.is_doubles == False,  # noqa: E712
            )
        ).first() > 0
    current_tournaments = [t for t in current_tournaments if _has_main_draw_played(t.id)]
    if not current_tournaments:
        # No matches this week → no movement. Return rows with zero delta.
        out = [
            LiveRow(
                rank=r.rank, points=r.points,
                projected_rank=r.rank,
                projected_points=r.points or 0,
                points_change=0,
                player_id=r.player_id, player=p,
            )
            for r, p in ranking_rows
        ]
        result = (latest_week, out)
        _CACHE[cache_key] = (time.monotonic(), result)
        return result

    current_tids = [t.id for t in current_tournaments]

    # All singles main-draw matches at the running tournaments — across
    # the whole tournament window, not just this week. A player who lost
    # in week 1 of a 2-week Slam still counts: their week-1 loss has
    # earned points and the prior-year same-tournament points still drop
    # off when this year's edition completes.
    this_year_matches = session.exec(
        select(Match)
        .where(
            Match.tournament_id.in_(current_tids),
            Match.is_doubles == False,  # noqa: E712
            Match.round.in_(_MAIN_DRAW),
            (Match.player1_id.in_(player_id_set))
            | (Match.player2_id.in_(player_id_set)),
        )
    ).all()

    # Group: (tournament_id, player_id) → list of matches.
    grouped_now: dict[tuple[int, int], list[Match]] = defaultdict(list)
    for m in this_year_matches:
        if m.player1_id and m.player1_id in player_id_set:
            grouped_now[(m.tournament_id, m.player1_id)].append(m)
        if m.player2_id and m.player2_id in player_id_set:
            grouped_now[(m.tournament_id, m.player2_id)].append(m)

    # Defending = the same brand last year. Look up by canonical slug
    # (BRAND_ALIASES applied at row write time, so the slug == canonical).
    last_year_lookup: dict[tuple[str, int], int] = {}  # (slug, year-1) → tid
    for t in current_tournaments:
        prior = session.exec(
            select(Tournament).where(
                Tournament.slug == t.slug,
                Tournament.tour == tour,
                Tournament.year == t.year - 1,
            )
        ).first()
        if prior and prior.id is not None:
            last_year_lookup[(t.slug, t.year)] = prior.id

    prior_tids = list(last_year_lookup.values())
    last_year_matches: list[Match] = []
    if prior_tids:
        last_year_matches = session.exec(
            select(Match)
            .where(
                Match.tournament_id.in_(prior_tids),
                Match.status.in_(
                    [MatchStatus.FINISHED, MatchStatus.RETIRED, MatchStatus.WALKOVER]
                ),
                Match.is_doubles == False,  # noqa: E712
                (Match.player1_id.in_(player_id_set))
                | (Match.player2_id.in_(player_id_set)),
            )
        ).all()

    grouped_prior: dict[tuple[int, int], list[Match]] = defaultdict(list)
    for m in last_year_matches:
        if m.player1_id and m.player1_id in player_id_set:
            grouped_prior[(m.tournament_id, m.player1_id)].append(m)
        if m.player2_id and m.player2_id in player_id_set:
            grouped_prior[(m.tournament_id, m.player2_id)].append(m)

    # Map current_tid → (category, last_year_tid).
    cat_by_current: dict[int, str | None] = {
        t.id: t.category.value if hasattr(t.category, "value") else (t.category or None)
        for t in current_tournaments
    }
    last_year_tid_by_current: dict[int, int | None] = {
        t.id: last_year_lookup.get((t.slug, t.year)) for t in current_tournaments
    }

    out: list[LiveRow] = []
    for r, p in ranking_rows:
        if p.id is None:
            continue
        earned = 0
        defending = 0
        for current_t in current_tournaments:
            tid = current_t.id
            cat = cat_by_current.get(tid)
            matches_now = grouped_now.get((tid, p.id), [])
            if matches_now:
                earned += _compute_earned(tour.value, cat, matches_now, p.id)
            last_year_tid = last_year_tid_by_current.get(tid)
            if last_year_tid is not None:
                matches_prior = grouped_prior.get((last_year_tid, p.id), [])
                if matches_prior:
                    defending += _compute_defended(tour.value, cat, matches_prior, p.id)
        change = earned - defending
        out.append(LiveRow(
            rank=r.rank, points=r.points,
            projected_rank=0,  # filled after sort
            projected_points=(r.points or 0) + change,
            points_change=change,
            player_id=p.id, player=p,
        ))

    out.sort(
        key=lambda x: (-x.projected_points, x.rank)
    )
    for i, row in enumerate(out, start=1):
        row.projected_rank = i

    result = (latest_week, out)
    _CACHE[cache_key] = (time.monotonic(), result)
    return result


def _compute_earned(
    tour: str, category: str | None, matches: list[Match], player_id: int,
) -> int:
    """How many points the player has locked in at this tournament so far.

    "Locked in" = points from the deepest round they've reached AND won;
    if they haven't lost yet, they're guaranteed at least the next round's
    *loser* points.
    """
    if not matches:
        return 0
    # Find the deepest round and whether the player won that match.
    deepest_match = max(matches, key=lambda m: round_depth(m.round))
    deepest_round = round_abbrev(deepest_match.round)
    if not deepest_round:
        return 0
    won = deepest_match.winner_id == player_id
    if deepest_match.status not in (
        MatchStatus.FINISHED, MatchStatus.RETIRED, MatchStatus.WALKOVER,
    ):
        # In-progress / scheduled — fall back to the previous (won)
        # round to avoid prematurely crediting this one.
        prior_completed = [
            m for m in matches
            if m.status in (
                MatchStatus.FINISHED, MatchStatus.RETIRED, MatchStatus.WALKOVER,
            )
        ]
        if not prior_completed:
            return 0
        prior = max(prior_completed, key=lambda m: round_depth(m.round))
        prior_round = round_abbrev(prior.round)
        prior_won = prior.winner_id == player_id
        if not prior_won:
            # Lost their last completed match — eliminated. Score the
            # round they lost in.
            return points_for_result(tour, category, prior_round)
        # Still in — credit the lock-in for the NEXT round's loser.
        return available_for_round(tour, category, prior_round)

    if won:
        # Won their latest match. If it's the final, that's a title.
        # Otherwise they're still alive in the next round.
        if deepest_round == "F":
            return points_for_result(tour, category, "W")
        return available_for_round(tour, category, deepest_round)
    # They lost their latest match. Score the round they lost in.
    return points_for_result(tour, category, deepest_round)


def _compute_defended(
    tour: str, category: str | None, matches: list[Match], player_id: int,
) -> int:
    """Points the player earned at the same tournament last year."""
    if not matches:
        return 0
    deepest = max(matches, key=lambda m: round_depth(m.round))
    deepest_round = round_abbrev(deepest.round)
    won_deepest = deepest.winner_id == player_id
    result = compute_player_result(deepest_round, won_deepest)
    return points_for_result(tour, category, result)
