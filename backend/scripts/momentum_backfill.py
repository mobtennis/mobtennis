"""Backfill momentum_json for one or more matches from api-tennis pbp.

Momentum is normally computed on the live-sync path. This one-shot fills it
for historical / imported rows (which have no api-tennis id on our side) by
fetching the point-by-point directly by provider match key, resolving the
player orientation to our match.player1, and storing the series.

Usage:
    # by our match id + explicit provider event key (for imported rows):
    python -m scripts.momentum_backfill --match-id 23472 --event-key 12040921

    # by our match id, when the row already carries an api_tennis_id:
    python -m scripts.momentum_backfill --match-id 456

    # also persist the resolved event key back onto the row:
    python -m scripts.momentum_backfill --match-id 23472 --event-key 12040921 --set-api-id
"""

from __future__ import annotations

import argparse
import asyncio
import json

from sqlmodel import Session

from app.db.session import engine, init_db
from app.models.match import Match, MatchStatus
from app.models.player import Player
from app.services.live import get_live_provider
from app.services.momentum import compute_momentum


def _surname(name: str | None) -> str:
    return (name or "").strip().split()[-1].lower() if name else ""


async def _fetch_pbp(event_key: str) -> list | None:
    provider = get_live_provider()
    try:
        return await provider.fetch_match_pbp(event_key)
    finally:
        close = getattr(provider, "aclose", None)
        if close:
            await close()


def backfill(match_id: int, event_key: str | None, set_api_id: bool) -> None:
    init_db()
    with Session(engine) as session:
        m = session.get(Match, match_id)
        if not m:
            raise SystemExit(f"match {match_id} not found")
        key = event_key or m.api_tennis_id
        if not key:
            raise SystemExit("no event key: pass --event-key or ensure the row has api_tennis_id")

        pbp = asyncio.run(_fetch_pbp(str(key)))
        if not pbp:
            raise SystemExit(f"no point-by-point returned for event key {key}")

        # Resolve orientation: does api-tennis "First Player" == our player1?
        # api's per-game rows only say First/Second; the names live on the
        # fixture row, which we don't refetch here — so infer from the running
        # game score of the last game vs. our stored winner, falling back to
        # a name check when we can pull the fixture. Simplest robust signal:
        # compare provider first/second surnames if available on the row.
        p1 = session.get(Player, m.player1_id) if m.player1_id else None
        p2 = session.get(Player, m.player2_id) if m.player2_id else None
        first_is_player1 = _resolve_orientation(str(key), p1, p2)

        payload = compute_momentum(
            pbp,
            complete=m.status == MatchStatus.FINISHED,
            first_is_player1=first_is_player1,
        )
        if payload is None:
            raise SystemExit("momentum computation produced nothing")

        m.momentum_json = json.dumps(payload)
        if set_api_id and event_key and not m.api_tennis_id:
            m.api_tennis_id = str(event_key)
        session.add(m)
        session.commit()

        p1n = p1.full_name if p1 else "P1"
        p2n = p2.full_name if p2 else "P2"
        lead = {1: p1n, 2: p2n, 0: "even"}[payload["leader"]]
        print(
            f"match {match_id}: {p1n} vs {p2n} — {payload['n_games']} games, "
            f"final {payload['final']:+.0f} (→ {lead}), "
            f"first_is_player1={first_is_player1}"
        )


def _resolve_orientation(event_key: str, p1: Player | None, p2: Player | None) -> bool:
    """True if api-tennis First Player == our player1. Compares surnames on
    the fixture row; defaults True (the live-sync convention)."""
    if not p1 or not p2:
        return True

    async def _fixture() -> dict | None:
        provider = get_live_provider()
        try:
            call = getattr(provider, "_call", None)
            if not call:
                return None
            rows = await call("get_fixtures", match_key=event_key)
            return rows[0] if rows else None
        finally:
            close = getattr(provider, "aclose", None)
            if close:
                await close()

    row = asyncio.run(_fixture())
    if not row:
        return True
    first_sn = _surname(row.get("event_first_player"))
    if not first_sn:
        return True
    return first_sn == _surname(p1.full_name)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--match-id", type=int, required=True)
    ap.add_argument("--event-key", type=str, default=None)
    ap.add_argument("--set-api-id", action="store_true")
    args = ap.parse_args()
    backfill(args.match_id, args.event_key, args.set_api_id)
