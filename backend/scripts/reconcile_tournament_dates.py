"""Reconcile catalog tournament dates with observed match data.

Walks every tournament in the catalog. For each, sets start_date /
end_date to min / max of observed main-draw scheduled_at when they
diverge from the catalog values by more than 2 days.

Idempotent. Same logic the scheduler runs hourly; this script is the
on-demand version.

Usage:
  uv run python -m scripts.reconcile_tournament_dates
"""

import logging

from sqlmodel import Session

from app.db.session import engine, init_db
from app.services.tournament_dates_reconcile import reconcile_tournament_dates

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("reconcile_tournament_dates")


def main() -> None:
    init_db()
    with Session(engine) as session:
        summary = reconcile_tournament_dates(session)
    log.info(
        "reconcile complete: %d checked, %d starts updated, %d ends updated",
        summary["checked"], summary["start_updated"], summary["end_updated"],
    )


if __name__ == "__main__":
    main()
