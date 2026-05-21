"""Apply the static career-high ranking seed.

Updates Player.career_high_rank from app/services/player_career_seed.py.
Only writes when the seed value is better (lower number) than what we
already have, so re-runs are safe and the live rankings sync going
forward can still improve values that drift below the seed.

Usage:
  uv run python -m scripts.seed_player_career_highs
"""

import logging

from sqlmodel import Session

from app.db.session import engine, init_db
from app.services.player_career_seed import apply_seed

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("seed_player_career_highs")


def main() -> None:
    init_db()
    with Session(engine) as session:
        summary = apply_seed(session)
    log.info(
        "seed complete: %d updated, %d skipped (better already), %d missing",
        summary["updated"],
        summary["skipped_already_better"],
        summary["missing_players"],
    )


if __name__ == "__main__":
    main()
