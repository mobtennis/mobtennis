"""Repair stale / wrong Player.bio text.

For players whose bio doesn't mention their own surname (a strong
sign the bio was scraped from the wrong Wikipedia article — see the
"D. Kasatkina got the list-of-players article" pattern), fetch the
correct lead extract and write it back. Idempotent.

Usage:
  uv run python -m scripts.repair_player_bios
  uv run python -m scripts.repair_player_bios --top 100
"""

import argparse
import asyncio
import logging

from sqlmodel import Session

from app.db.session import engine, init_db
from app.services.players_bio_repair import repair_top_n

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("repair_player_bios")


async def _run(top: int) -> None:
    with Session(engine) as session:
        attempted, repaired, untouched = await repair_top_n(session, n=top)
    log.info(
        "repair complete: %d attempted, %d repaired, %d untouched",
        attempted, repaired, untouched,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=int, default=250)
    args = parser.parse_args()
    init_db()
    asyncio.run(_run(args.top))


if __name__ == "__main__":
    main()
