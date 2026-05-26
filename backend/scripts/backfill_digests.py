"""Generate editorial digests for past weeks.

Usage:
  uv run python -m scripts.backfill_digests              # all of YTD
  uv run python -m scripts.backfill_digests --year 2025  # specific year
  uv run python -m scripts.backfill_digests --from 2026-01-05 --to 2026-04-27
  uv run python -m scripts.backfill_digests --force      # overwrite existing rows

Walks Mondays in the requested range and calls generate_digest() for
each. ANTHROPIC_API_KEY must be set; otherwise the service skips with
a warning and the script logs zero writes.
"""

import argparse
import logging
import time
from datetime import date, timedelta

from sqlmodel import Session

from app.db.session import engine, init_db
from app.services.editorial_digest import generate_digest_for_week, monday_of

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("backfill_digests")


def _mondays_in_range(start: date, end: date):
    cur = monday_of(start)
    end = monday_of(end)
    while cur <= end:
        yield cur
        cur += timedelta(days=7)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, help="Backfill all weeks of a year.")
    parser.add_argument("--from", dest="from_date", help="Start date (YYYY-MM-DD).")
    parser.add_argument("--to", dest="to_date", help="End date (YYYY-MM-DD).")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate even if a row already exists for the week.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=1.0,
        help="Seconds to sleep between API calls. Default 1.0.",
    )
    args = parser.parse_args()

    today = date.today()
    if args.year:
        start = date(args.year, 1, 1)
        end = min(today, date(args.year, 12, 31))
    elif args.from_date or args.to_date:
        start = date.fromisoformat(args.from_date) if args.from_date else date(today.year, 1, 1)
        end = date.fromisoformat(args.to_date) if args.to_date else today
    else:
        start = date(today.year, 1, 1)
        end = today

    init_db()
    written = 0
    skipped = 0
    failed = 0

    with Session(engine) as session:
        for monday in _mondays_in_range(start, end):
            # Don't generate for the current week — it isn't over yet,
            # the recap would be incomplete.
            if monday >= monday_of(today):
                continue
            try:
                row = generate_digest_for_week(session, monday, force=args.force)
                if row is None:
                    skipped += 1
                    log.info("week %s: skipped (no data or LLM unavailable)", monday)
                else:
                    written += 1
                    log.info("week %s: %s", monday, row.headline)
            except Exception:
                failed += 1
                log.exception("week %s: failed", monday)
            time.sleep(args.sleep)

    log.info("backfill complete: %d written, %d skipped, %d failed", written, skipped, failed)


if __name__ == "__main__":
    main()
