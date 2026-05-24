"""Reconcile Tournament.start_date / end_date with observed match data.

The static seed in `tournament_seed.py` and Wikipedia-derived dates
sometimes lag reality:
  - Slams switched to a 14-day Sunday-start format in 2024 — our seed
    still had Monday starts encoded.
  - Wikipedia dates are sometimes the "official" date which can differ
    from when matches actually start (qualifying / show matches).
  - api-tennis publishes match schedules a few days before the formal
    start, so `min(scheduled_at)` is the most reliable signal.

Rule: if the earliest main-draw match scheduled_at for a tournament
predates the catalog start_date — or is more than 2 days after — pull
the catalog into line with the data.

We bias toward observed match data because:
  - It comes from the live feed, which is authoritative for "what's
    actually being played"
  - The static seed is a typical-year guess; year-to-year reality
    diverges (different sponsors push dates around, COVID years
    shifted everything, the 14-day Slam format etc.)
  - End-date is similarly drawn from `max(scheduled_at)` over the
    main draw.

Idempotent. Cheap (one query group-by tournament). Safe to run hourly
in the scheduler.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlmodel import Session, func, select

from app.models.match import Match, MatchStatus
from app.models.tournament import Tournament

log = logging.getLogger(__name__)

# Round labels we consider "main draw" for date inference. Qualifying
# rounds (Q1/Q2/Q3) happen before the formal start and would pull
# start_date too early.
_MAIN_DRAW = (
    "R128", "R64", "R32", "R16", "QF", "SF", "F",
    "first round", "second round", "third round", "fourth round",
    "1/64-finals", "1/32-finals", "1/16-finals", "1/8-finals",
    "quarter-finals", "semi-finals", "final",
)

# Drift tolerance — we only rewrite when observed dates are more than
# this many days away from the catalog dates. Keeps minor scheduling
# slop from churning the catalog.
_TOLERANCE = timedelta(days=2)


def reconcile_tournament_dates(session: Session) -> dict:
    """Walk every tournament with at least one main-draw match in the
    catalog. For each, derive start = min(scheduled_at), end = max(
    scheduled_at), and overwrite the catalog when divergence exceeds
    tolerance.

    Verbose-prefixed api-tennis round strings (e.g. "ATP French Open -
    1/64-finals") are included via a SQL LIKE pass below.
    """
    # Per-tournament min/max of main-draw scheduled_at.
    # Build a coarse filter: round is in our exact list OR ends with one
    # of the verbose-format suffixes. SQLAlchemy doesn't have a clean
    # IN-OR-LIKE composition, so we do two queries and merge.
    exact_rows = session.exec(
        select(
            Match.tournament_id,
            func.min(Match.scheduled_at),
            func.max(Match.scheduled_at),
        )
        .where(
            Match.round.in_(_MAIN_DRAW),
            Match.scheduled_at.is_not(None),
            Match.is_doubles == False,  # noqa: E712
        )
        .group_by(Match.tournament_id)
    ).all()
    like_rows = session.exec(
        select(
            Match.tournament_id,
            func.min(Match.scheduled_at),
            func.max(Match.scheduled_at),
        )
        .where(
            Match.round.like("% - 1/%-finals")
            | Match.round.like("% - quarter-finals")
            | Match.round.like("% - semi-finals")
            | Match.round.like("% - final")
            | Match.round.like("% - first round")
            | Match.round.like("% - second round")
            | Match.round.like("% - third round")
            | Match.round.like("% - fourth round"),
            Match.scheduled_at.is_not(None),
            Match.is_doubles == False,  # noqa: E712
        )
        .group_by(Match.tournament_id)
    ).all()

    # Merge — take the wider window across both sources.
    observed: dict[int, tuple[date, date]] = {}
    for tid, mn, mx in list(exact_rows) + list(like_rows):
        if tid is None or mn is None or mx is None:
            continue
        prev = observed.get(tid)
        new_min = mn.date() if hasattr(mn, "date") else mn
        new_max = mx.date() if hasattr(mx, "date") else mx
        if prev is None:
            observed[tid] = (new_min, new_max)
        else:
            observed[tid] = (min(prev[0], new_min), max(prev[1], new_max))

    if not observed:
        return {"checked": 0, "start_updated": 0, "end_updated": 0}

    tournaments = session.exec(
        select(Tournament).where(Tournament.id.in_(list(observed.keys())))
    ).all()

    start_updated = end_updated = 0
    for t in tournaments:
        if t.id is None:
            continue
        obs_start, obs_end = observed[t.id]
        changed = False
        # start_date
        if (
            t.start_date is None
            or abs(t.start_date - obs_start) > _TOLERANCE
        ):
            if t.start_date != obs_start:
                log.info(
                    "%s %s: start_date %s -> %s (from observed matches)",
                    t.slug, t.year, t.start_date, obs_start,
                )
                t.start_date = obs_start
                start_updated += 1
                changed = True
        # end_date
        if (
            t.end_date is None
            or abs(t.end_date - obs_end) > _TOLERANCE
        ):
            if t.end_date != obs_end:
                log.info(
                    "%s %s: end_date %s -> %s (from observed matches)",
                    t.slug, t.year, t.end_date, obs_end,
                )
                t.end_date = obs_end
                end_updated += 1
                changed = True
        if changed:
            session.add(t)
    session.commit()
    return {
        "checked": len(observed),
        "start_updated": start_updated,
        "end_updated": end_updated,
    }
