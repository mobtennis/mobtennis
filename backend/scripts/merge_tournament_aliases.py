"""Merge alias-slug Tournament rows into their canonical brand row.

Run once after seeding a new entry in BRAND_ALIASES (see
`app/services/tournament_resolver.py`). Idempotent — re-runs are
no-ops once the catalog is clean.

Usage:
  uv run python -m scripts.merge_tournament_aliases
"""

import logging

from sqlmodel import Session

from app.db.session import engine, init_db
from app.services.tournament_resolver import merge_duplicates

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("merge_tournament_aliases")


def main() -> None:
    init_db()
    with Session(engine) as session:
        summary = merge_duplicates(session)
    log.info(
        "merge complete: %d merged, %d renamed, %d matches moved",
        summary["merged"], summary["renamed"], summary["matches_moved"],
    )


if __name__ == "__main__":
    main()
