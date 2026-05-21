"""Enrich career_high_rank for the top players via Wikipedia infobox.

Walks the top-200 ATP + WTA by current_rank (i.e. top 200 of each
tour with non-null `wikipedia_url`), reads each player's Wikipedia
lead-section wikitext, regex-extracts the `careerhighsingles` field,
and updates Player.career_high_rank if it's better (lower) than the
stored value.

Rate-limited at 500ms per request → ~3-4 minutes for 400 players.
Idempotent: re-runs only overwrite when the parsed value beats the
stored one.

Usage:
  uv run python -m scripts.enrich_career_highs
  uv run python -m scripts.enrich_career_highs --top 50
"""

import argparse
import asyncio
import logging

from sqlmodel import Session

from app.db.session import engine, init_db
from app.services.players_career_high_enrich import enrich_top_n

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("enrich_career_highs")


async def _run(top: int) -> None:
    with Session(engine) as session:
        attempted, updated, skipped = await enrich_top_n(session, n=top)
    log.info(
        "enrich complete: %d attempted, %d updated, %d skipped",
        attempted, updated, skipped,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--top", type=int, default=200,
        help="Number of top players per tour to enrich. Default 200.",
    )
    args = parser.parse_args()
    init_db()
    asyncio.run(_run(args.top))


if __name__ == "__main__":
    main()
