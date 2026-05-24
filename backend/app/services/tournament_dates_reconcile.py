"""Reconcile Tournament.start_date / end_date with observed match data.

The static seed in `tournament_seed.py` and Wikipedia-derived dates
sometimes lag reality:
  - Slams switched to a 14-day Sunday-start format in 2024 — our seed
    still had Monday starts encoded.
  - Wikipedia dates are sometimes the "official" date which can differ
    from when matches actually start.

What we DON'T use as a signal:
  - Verbose api-tennis round labels like "ATP French Open -
    Quarter-finals". A first iteration of this service matched those
    via LIKE patterns and silently picked up QUALIFYING brackets,
    which api-tennis labels with the same final/semi/quarter
    nomenclature as the main draw (qualifying brackets have their own
    final). For French Open 2026, that pulled start_date a full week
    early to the start of qualifying matches.
  - Doubles matches — singles main draw defines the formal window.

What we DO use:
  - Short-form round codes from our Sackmann/Wikipedia bracket import
    (R128, R64, R32, R16, QF, SF, F). These come from a parsing
    pipeline that explicitly distinguishes main draw from qualifying,
    so they're trustworthy.

End-date rule — only EXTEND, never shrink:
  - api-tennis publishes match schedules a few days at a time, not
    the full two weeks of a Slam up front. So on Day 1 of a Slam our
    max(scheduled_at) is Day 1, not the Final. Shrinking the catalog
    end_date to today's max would give us "ends today" while the
    tournament is actually running for two more weeks.
  - Catalog end_date (from static seed or Wikipedia) is therefore
    the upper bound; observed data can only push it later.

Start-date rule:
  - When catalog start_date is None: use observed (any direction).
  - When catalog is set: rewrite if observed is within ±7 days but
    differs by >2 days. Differences larger than a week indicate
    misread data, not a real schedule change, and we keep the
    catalog.

Idempotent. Cheap (one indexed query). Safe to run hourly in the
scheduler.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlmodel import Session, func, select

from app.models.match import Match, MatchStatus
from app.models.tournament import Tournament

log = logging.getLogger(__name__)

# Short-form main-draw round codes only. Set by our Sackmann import
# + Wikipedia bracket parser, both of which distinguish main draw
# from qualifying. Verbose api-tennis labels (e.g. "ATP French Open
# - Quarter-finals") are EXCLUDED on purpose — those apply equally
# to the qualifying-bracket finals and would pull start_date a week
# too early.
_MAIN_DRAW = (
    "R128", "R64", "R32", "R16", "QF", "SF", "F",
)

# Drift tolerance — we only rewrite when observed dates are more than
# this many days away from the catalog dates. Keeps minor scheduling
# slop from churning the catalog.
_TOLERANCE = timedelta(days=2)

# Sanity ceiling for start-date drift. If observed start differs from
# catalog by more than this much, treat as suspect data (probably an
# api-tennis labeling glitch or an off-by-year row) and keep the
# catalog. Six days covers genuine Sunday/Monday Slam-start shifts.
_MAX_START_DRIFT = timedelta(days=6)


def reconcile_tournament_dates(session: Session) -> dict:
    """Update Tournament.start_date / end_date from observed main-draw
    match data, using short-form round codes only.

    See module docstring for the start/end rules. Idempotent."""
    rows = session.exec(
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
    observed: dict[int, tuple[date, date]] = {}
    for tid, mn, mx in rows:
        if tid is None or mn is None or mx is None:
            continue
        observed[tid] = (
            mn.date() if hasattr(mn, "date") else mn,
            mx.date() if hasattr(mx, "date") else mx,
        )
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

        # ---- start_date --------------------------------------------------
        # Catalog None → take observed. Otherwise update only when the
        # drift is meaningful (>tolerance) and bounded (within max-drift
        # — beyond that the data is suspect).
        if t.start_date is None:
            log.info("%s %s: start_date None -> %s", t.slug, t.year, obs_start)
            t.start_date = obs_start
            start_updated += 1
            changed = True
        elif (
            abs(t.start_date - obs_start) > _TOLERANCE
            and abs(t.start_date - obs_start) <= _MAX_START_DRIFT
            and t.start_date != obs_start
        ):
            log.info(
                "%s %s: start_date %s -> %s",
                t.slug, t.year, t.start_date, obs_start,
            )
            t.start_date = obs_start
            start_updated += 1
            changed = True

        # ---- end_date — extend only --------------------------------------
        # Never shrink end_date: api-tennis releases its schedule
        # rolling, so on Day 1 of a Slam our max(scheduled_at) is just
        # Day 1, not the Final. Shrinking would give a "ends today"
        # window for a tournament running another 13 days.
        if t.end_date is None and obs_end:
            log.info("%s %s: end_date None -> %s", t.slug, t.year, obs_end)
            t.end_date = obs_end
            end_updated += 1
            changed = True
        elif (
            t.end_date is not None
            and obs_end > t.end_date
            and (obs_end - t.end_date) <= _MAX_START_DRIFT
        ):
            log.info(
                "%s %s: end_date %s -> %s (extending)",
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
