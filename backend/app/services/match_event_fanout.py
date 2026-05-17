"""Fan match events out to push subscribers.

Lookup pattern per event:
  match_follows (filtered by granularity) → user_tokens
  push_tokens (joined by user_token)       → expo_tokens
  → Expo push API

After a match_end, we delete the corresponding match_follow rows so the
follow is genuinely transient (the user opted in for *this* match only).

Session discipline: we do all DB reads + cleanup writes in tightly-scoped
sessions and call send_push() *outside* of any session. Earlier this
function held a session open across every Expo API call in the batch,
which kept a connection from the pool busy for seconds — under live load
this was the dominant source of pool exhaustion.
"""

from __future__ import annotations

import logging

from sqlmodel import Session, select

from app.db.session import engine
from app.models.match_follow import MatchFollow, MatchFollowGranularity
from app.models.push_token import PushToken
from app.services.match_events import KEY_MOMENT_KINDS, MatchEvent
from app.services.push import send_push

log = logging.getLogger(__name__)


def _granularities_for(kind: str) -> set[MatchFollowGranularity]:
    """Which granularities should receive an event of this kind?

    KEY_MOMENTS gets the dramatic events; EVERY_GAME gets those plus the
    per-game pings. We never deliver `game_end` to KEY_MOMENTS subscribers.
    """
    if kind in KEY_MOMENT_KINDS:
        return {MatchFollowGranularity.KEY_MOMENTS, MatchFollowGranularity.EVERY_GAME}
    if kind == "game_end":
        return {MatchFollowGranularity.EVERY_GAME}
    return set()


async def fan_out(events: list[MatchEvent]) -> int:
    """Send notifications for the given events. Returns count delivered."""
    if not events:
        return 0

    # Phase 1: gather everything we need with the session open, then close it.
    batches: list[list[dict]] = []
    terminal_match_ids: set[int] = set()
    with Session(engine) as session:
        for event in events:
            if event.kind == "match_end":
                terminal_match_ids.add(event.match_id)

            wanted = _granularities_for(event.kind)
            if not wanted:
                continue

            follows = session.exec(
                select(MatchFollow).where(
                    MatchFollow.match_id == event.match_id,
                    MatchFollow.granularity.in_(list(wanted)),
                )
            ).all()
            if not follows:
                continue

            user_tokens = [f.user_token for f in follows]
            tokens = session.exec(
                select(PushToken).where(PushToken.user_token.in_(user_tokens))
            ).all()
            if not tokens:
                continue

            batches.append([
                {
                    "to": pt.expo_token,
                    "title": event.title,
                    "body": event.body,
                    "data": {"match_id": event.match_id, "kind": event.kind},
                    "sound": "default",
                }
                for pt in tokens
            ])

    # Phase 2: HTTP push without holding any DB connection.
    sent = 0
    for batch in batches:
        try:
            await send_push(batch)
            sent += len(batch)
        except Exception:
            log.exception("fan-out send failed for batch of %d", len(batch))

    # Phase 3: cleanup writes. Auto-purge follows for matches that just ended.
    if terminal_match_ids:
        with Session(engine) as session:
            purged = session.exec(
                select(MatchFollow).where(MatchFollow.match_id.in_(list(terminal_match_ids)))
            ).all()
            for f in purged:
                session.delete(f)
            session.commit()
            if purged:
                log.info("match-follow purge: %d rows for %d ended matches",
                         len(purged), len(terminal_match_ids))

    return sent
