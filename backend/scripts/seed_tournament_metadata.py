"""Apply the static tournament metadata seed.

For each entry in `app/services/tournament_seed.py::SEEDS`, fills NULL
columns on every Tournament row matching the slug. Existing values
from auto-enrichment passes (Wikipedia / Wikidata) are never overwritten.

Idempotent.

Usage:
  uv run python -m scripts.seed_tournament_metadata
  uv run python -m scripts.seed_tournament_metadata --year 2026
"""

import argparse
import logging

from sqlmodel import Session

from app.db.session import engine, init_db
from app.services.tournament_seed import apply_seeds

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("seed_tournament_metadata")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, help="Restrict to a single year.")
    args = parser.parse_args()

    init_db()
    with Session(engine) as session:
        summary = apply_seeds(session, year=args.year)
    log.info(
        "seed complete: %d rows updated, %d fields filled",
        summary["rows_updated"], summary["fields_set"],
    )


if __name__ == "__main__":
    main()
