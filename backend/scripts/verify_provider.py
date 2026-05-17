"""Smoke-test the configured live provider.

Usage:
  API_TENNIS_KEY=xxxx python -m scripts.verify_provider           # uses .env
  python -m scripts.verify_provider --raw                         # dump first row verbatim

Prints what the provider sees right now: live count, tomorrow count, a few
sample rows in `LiveMatch` form. Useful for debugging keys / mappings before
wiring the full backend. No DB, no server.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict

# Allow running as `python -m scripts.verify_provider` from backend/
# or as `python scripts/verify_provider.py`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.services.live import get_live_provider


async def main(raw: bool, today_too: bool) -> int:
    if not settings.api_tennis_key:
        print("✗ No API_TENNIS_KEY configured. Set it in .env then re-run.")
        return 1

    provider = get_live_provider()
    print(f"→ Provider: {provider.name}")
    print(f"→ Endpoint: {settings.api_tennis_base_url}")
    print()

    try:
        live = await provider.fetch_live()
    except Exception as e:
        print(f"✗ fetch_live() failed: {type(e).__name__}: {e}")
        return 2

    print(f"✓ fetch_live(): {len(live)} match{'es' if len(live) != 1 else ''}")
    for m in live[:5]:
        p1 = m.player1_name or "?"
        p2 = m.player2_name or "?"
        score = m.score or "0-0"
        print(f"   [{m.tour.upper()}] {m.tournament_name} · {m.round or '–'}")
        print(f"       {p1}  vs  {p2}   {score}    [{m.status}]")
        if m.current_game:
            print(f"       game: {m.current_game}    serve: P{m.server or '?'}")

    if today_too:
        print()
        try:
            today = await provider.fetch_today()
            print(f"✓ fetch_today(): {len(today)} fixture{'s' if len(today) != 1 else ''}")
            for m in today[:5]:
                print(f"   [{m.tour.upper()}] {m.tournament_name} · {m.scheduled_at} · {m.player1_name} vs {m.player2_name} [{m.status}]")
        except Exception as e:
            print(f"✗ fetch_today() failed: {type(e).__name__}: {e}")

    if raw and live:
        print()
        print("--- Raw first row (provider native) ---")
        print(json.dumps(live[0].raw, indent=2)[:2000])
        print()
        print("--- Mapped first row (LiveMatch) ---")
        d = asdict(live[0])
        d.pop("raw", None)
        print(json.dumps(d, indent=2, default=str))

    if hasattr(provider, "aclose"):
        await provider.aclose()
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", action="store_true", help="Print raw + mapped first row")
    parser.add_argument("--no-today", action="store_true", help="Skip fetch_today()")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(raw=args.raw, today_too=not args.no_today)))
