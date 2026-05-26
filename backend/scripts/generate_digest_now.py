"""Trigger an ad-hoc digest right now.

Covers the window from the last digest's `period_end` through the
current moment. Enforces the 24h rate-limit unless `--force`.

Usage:
  uv run python -m scripts.generate_digest_now
  uv run python -m scripts.generate_digest_now --force
  uv run python -m scripts.generate_digest_now --note "Some milestone to weave in"
"""

import argparse
import logging

from sqlmodel import Session

from app.db.session import engine, init_db
from app.services.editorial_digest import generate_digest

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("generate_digest_now")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true",
                        help="Bypass the 24h rate-limit / same-day uniqueness gate.")
    parser.add_argument("--note", action="append", default=[],
                        help="Verified human-supplied fact to weave into the recap. "
                             "Repeatable. Stored in source_json for audit.")
    args = parser.parse_args()

    init_db()
    with Session(engine) as session:
        result = generate_digest(
            session,
            force=args.force,
            editorial_notes=args.note or None,
        )
    if result.status == "created":
        log.info("DIGEST CREATED — %s", result.row.headline)
        log.info("  anchor:        /digest/%s", result.row.week_start)
        log.info("  period:        %s → %s",
                 result.row.period_start, result.row.period_end)
    elif result.status == "skipped_rate_limited":
        log.warning("SKIPPED (rate-limited): %s", result.message)
    elif result.status == "skipped_no_facts":
        log.info("SKIPPED (no facts): %s", result.message)
    else:
        log.error("FAILED: %s", result.message)


if __name__ == "__main__":
    main()
