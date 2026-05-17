"""Fan match start/end events out to player + tournament followers.

Sibling of `match_event_fanout` but covers a different audience:
  match_event_fanout  → users who explicitly opted into a *single match*
  follow_event_fanout → users who follow a *player* or *tournament*

We deliver only the headline transitions (match_start, match_end) to follow
audiences — set ends and breaks of serve would be too noisy for someone who
just wants to know when their player plays. Match-follows still get the full
event stream via `match_event_fanout`.
"""

from __future__ import annotations

import logging

from sqlmodel import Session, select

from app.db.session import engine
from app.models.follow import Follow, FollowKind
from app.models.match import Match
from app.models.player import Player
from app.models.push_token import PushToken
from app.models.tournament import Tournament
from app.services.match_events import MatchEvent
from app.services.push import send_push

log = logging.getLogger(__name__)

# Only these events warrant fan-out to broad audiences. Set/game/break-level
# events are too noisy for users following a player or tournament.
BROADCAST_KINDS: set[str] = {"match_start", "match_end"}


async def fan_out(events: list[MatchEvent]) -> int:
    """Send player+tournament-follow notifications. Returns count delivered.

    Reads are confined to a single session block; HTTP fan-out happens
    afterwards with no DB connection held. Same rationale as
    match_event_fanout: connection-per-message during HTTP loops was the
    dominant cause of pool exhaustion in prod.
    """
    if not events:
        return 0

    # Phase 1: build all outbound batches with the session open.
    batches: list[list[dict]] = []
    with Session(engine) as session:
        for event in events:
            if event.kind not in BROADCAST_KINDS:
                continue
            match = session.get(Match, event.match_id)
            if not match:
                continue

            p1 = session.get(Player, match.player1_id) if match.player1_id else None
            p2 = session.get(Player, match.player2_id) if match.player2_id else None
            tournament = session.get(Tournament, match.tournament_id)

            # Build one message per user_token. Player-perspective wins over
            # tournament-perspective for the same user (more relevant phrasing).
            msgs: dict[str, dict] = {}

            for slot, player in ((1, p1), (2, p2)):
                if not player:
                    continue
                opp = p2 if slot == 1 else p1
                opp_name = opp.full_name if opp else "their opponent"
                tournament_name = tournament.name if tournament else ""
                round_str = match.round or ""
                if tournament_name and round_str:
                    context = f"{tournament_name} · {round_str}"
                else:
                    context = tournament_name or round_str

                title, body = _player_message(event, player.full_name, opp_name, context, match, slot)
                for ut in _resolve_player_followers(session, player.slug):
                    msgs.setdefault(ut, {
                        "title": title,
                        "body": body,
                        "data": {"match_id": event.match_id, "kind": event.kind, "via": "player"},
                    })

            if tournament:
                t_title, t_body = _tournament_message(event, tournament.name, match, p1, p2)
                tour_value = tournament.tour.value if tournament.tour else None
                for ut in _resolve_tournament_followers(session, tournament.slug, tour_value):
                    if ut in msgs:
                        continue
                    msgs[ut] = {
                        "title": t_title,
                        "body": t_body,
                        "data": {"match_id": event.match_id, "kind": event.kind, "via": "tournament"},
                    }

            if not msgs:
                continue

            user_tokens = list(msgs.keys())
            push_tokens = session.exec(
                select(PushToken).where(PushToken.user_token.in_(user_tokens))
            ).all()
            if not push_tokens:
                continue

            batch = []
            for pt in push_tokens:
                m = msgs.get(pt.user_token)
                if not m:
                    continue
                batch.append({
                    "to": pt.expo_token,
                    "title": m["title"],
                    "body": m["body"],
                    "data": m["data"],
                    "sound": "default",
                })
            if batch:
                batches.append(batch)

    # Phase 2: HTTP without any DB connection held.
    sent = 0
    for batch in batches:
        try:
            await send_push(batch)
            sent += len(batch)
        except Exception:
            log.exception("follow fan-out send failed for batch of %d", len(batch))

    return sent


def _resolve_player_followers(session: Session, player_slug: str) -> list[str]:
    rows = session.exec(
        select(Follow).where(
            Follow.kind == FollowKind.PLAYER,
            Follow.target_slug == player_slug,
        )
    ).all()
    return [r.user_token for r in rows]


def _resolve_tournament_followers(session: Session, slug: str, tour: str | None) -> list[str]:
    stmt = select(Follow).where(
        Follow.kind == FollowKind.TOURNAMENT,
        Follow.target_slug == slug,
    )
    if tour is not None:
        stmt = stmt.where(Follow.target_tour == tour)
    rows = session.exec(stmt).all()
    return [r.user_token for r in rows]


def _player_message(
    event: MatchEvent,
    player_name: str,
    opp_name: str,
    context: str,
    match: Match,
    slot: int,
) -> tuple[str, str]:
    """Compose a notification from the followed player's perspective.

    `slot` is 1 if the followed player is player1, 2 if player2 — used to
    decide if they won by comparing against match.winner_id directly.
    """
    if event.kind == "match_start":
        title = f"{player_name} on court"
        body = f"vs {opp_name}{' · ' + context if context else ''}"
        return title, body

    score = match.score or ""
    won = (
        match.winner_id is not None
        and (
            (slot == 1 and match.winner_id == match.player1_id)
            or (slot == 2 and match.winner_id == match.player2_id)
        )
    )
    status = match.status.value
    if status in ("retired", "walkover"):
        title = f"{player_name}: {status}"
        body = f"{opp_name}{' — ' + score if score else ''}"
    elif won:
        title = f"{player_name} wins"
        body = f"def. {opp_name} {score}".strip()
    else:
        title = f"{player_name} is out"
        body = f"lost to {opp_name} {score}".strip()
    if context:
        body = f"{body} · {context}"
    return title, body


def _tournament_message(
    event: MatchEvent,
    tournament_name: str,
    match: Match,
    p1: Player | None,
    p2: Player | None,
) -> tuple[str, str]:
    p1_name = p1.full_name if p1 else "TBD"
    p2_name = p2.full_name if p2 else "TBD"
    round_str = match.round or ""
    if event.kind == "match_start":
        title = f"{tournament_name} underway"
        body = f"{p1_name} vs {p2_name}{' · ' + round_str if round_str else ''}"
        return title, body
    # match_end
    score = match.score or ""
    winner_name = None
    if match.winner_id is not None:
        if match.winner_id == match.player1_id:
            winner_name = p1_name
        elif match.winner_id == match.player2_id:
            winner_name = p2_name
    if winner_name:
        title = f"{tournament_name}"
        body = f"{winner_name} def. {(p2_name if winner_name == p1_name else p1_name)} {score}".strip()
    else:
        title = f"{tournament_name}"
        body = f"{p1_name} vs {p2_name} — {match.status.value} {score}".strip()
    if round_str:
        body = f"{body} · {round_str}"
    return title, body
