"""Show what api-tennis is actually returning for live matches right now.

Use to debug "the site is missing live matches I see on Google" type
issues — runs against the real provider, prints what we got back vs what
the upstream is saying.

Usage on the box:
  ssh mobtennis-ubuntu '\\
    sudo -u tennismob \\
    /opt/tennismob/backend/.venv/bin/python \\
    /opt/tennismob/backend/scripts/diagnose_live.py'

Filter to a specific tournament name fragment:
  ssh mobtennis-ubuntu 'sudo -u tennismob /opt/tennismob/backend/.venv/bin/python /opt/tennismob/backend/scripts/diagnose_live.py rome'
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path


def _load_env_file() -> None:
    """systemd's EnvironmentFile only fires for the actual service unit, so
    when this script runs ad-hoc via SSH we manually load /opt/tennismob/
    backend/.env so settings.api_tennis_key resolves."""
    env_file = Path(__file__).resolve().parents[1] / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env_file()

from app.services.live import get_live_provider  # noqa: E402


async def main() -> None:
    needle = sys.argv[1].lower() if len(sys.argv) > 1 else None

    provider = get_live_provider()
    if provider.name == "noop":
        print("No live provider configured (API_TENNIS_KEY missing?)")
        return

    rows = await provider.fetch_live()
    print(f"api-tennis returned {len(rows)} live matches total")

    if needle:
        rows = [m for m in rows if needle in (m.tournament_name or "").lower()]
        print(f"  filtered by '{needle}': {len(rows)} match(es)")
    print()

    if not rows:
        print("Nothing to show.")
        return

    for m in rows:
        live_flag = m.raw.get("event_live") if m.raw else "?"
        ev_status = m.raw.get("event_status") if m.raw else "?"
        winner = m.raw.get("event_winner") if m.raw else None
        print(f"  {m.tour:3} {m.tournament_name}")
        print(f"      round={m.round!r}")
        print(f"      {m.player1_name} vs {m.player2_name}")
        print(f"      our_status={m.status}  upstream: event_live={live_flag!r} "
              f"event_status={ev_status!r} winner={winner!r}")
        print(f"      score={m.score!r} scheduled_at={m.scheduled_at} key={m.provider_match_id}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
