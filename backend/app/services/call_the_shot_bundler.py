"""Bundle pool CallTheShotItems into 5-item daily sets.

Same shape as the STB/NTP bundlers:
  - finds unassigned, not-hidden items
  - sorts them for consistent pairing (currently by (video_id,
    start_at_s) — keeps same-video items contiguous so the seek-not-
    reload optimization in the round component kicks in)
  - groups into 5-item chunks
  - schedules each new set on the next available date (today or the
    day after the latest existing publish_date, whichever is later)

Idempotent — re-running doesn't disturb already-bundled items, and
short tails (fewer than 5 unassigned items) sit in the pool until
more arrive.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlmodel import Session, select

from app.models.call_the_shot import CallTheShotItem, CallTheShotSet

log = logging.getLogger(__name__)

ITEMS_PER_SET = 5


def _next_publish_date(session: Session) -> date:
    last = session.exec(
        select(CallTheShotSet.publish_date)
        .order_by(CallTheShotSet.publish_date.desc())
        .limit(1)
    ).first()
    today = date.today()
    if not last:
        return today
    return max(last + timedelta(days=1), today)


def bundle_cts(session: Session) -> list[CallTheShotSet]:
    """Form as many 5-item sets as the pool allows. Returns the new
    sets in publish-date order."""
    pool = session.exec(
        select(CallTheShotItem)
        .where(
            CallTheShotItem.is_hidden == False,  # noqa: E712
            CallTheShotItem.set_id.is_(None),
        )
        .order_by(CallTheShotItem.video_id, CallTheShotItem.start_at_s)
    ).all()

    sets_built: list[CallTheShotSet] = []
    i = 0
    while i + ITEMS_PER_SET <= len(pool):
        new_set = CallTheShotSet(
            publish_date=_next_publish_date(session),
            is_published=True,
        )
        session.add(new_set)
        session.flush()
        new_set.title = f"Round {new_set.id}"
        chunk = pool[i : i + ITEMS_PER_SET]
        for position, item in enumerate(chunk, start=1):
            item.set_id = new_set.id
            item.position = position
            session.add(item)
        session.commit()
        sets_built.append(new_set)
        log.info(
            "cts: bundled set %d (publish_date=%s) with %d items",
            new_set.id, new_set.publish_date, ITEMS_PER_SET,
        )
        i += ITEMS_PER_SET
    return sets_built
