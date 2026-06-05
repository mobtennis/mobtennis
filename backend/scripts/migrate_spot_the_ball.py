"""One-shot migration: SpotTheBallPuzzle → SpotTheBallSet + SpotTheBallImage.

Run on prod once after deploying the new model code. Idempotent — if
the old table doesn't exist or is already empty, it's a no-op.

Steps:
  1. Read every SpotTheBallPuzzle row (legacy schema)
  2. Create a SpotTheBallImage row mirroring each — published rows
     keep is_inpainted=True; queued rows arrive as is_inpainted=False
  3. Run the bundler to group inpainted images into sets of 5
     (no duplicate player per set)
  4. Drop the legacy spot_the_ball_puzzles table

Notes:
  - Files in web/public/spot-the-ball/ KEEP their old date-based
    names. image_url on the new image rows points at the same URL.
    Renaming files to {image_id}.jpg is a separate concern; the
    naming-by-date is now just a quirk of the file system, not
    user-facing.
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlmodel import Session, select

from app.db.session import engine, init_db
from app.models.spot_the_ball import SpotTheBallImage
from app.services.spot_the_ball_bundler import bundle_pool

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("migrate_spot_the_ball")


def _legacy_table_exists(session: Session) -> bool:
    row = session.exec(
        text(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='spot_the_ball_puzzles'"
        )
    ).first()
    return row is not None


def main() -> None:
    init_db()
    with Session(engine) as session:
        if not _legacy_table_exists(session):
            log.info("legacy table not present — nothing to migrate")
            return

        # Read every legacy row.
        legacy = session.exec(text(
            "SELECT puzzle_date, image_url, original_image_url, image_w, image_h, "
            "ball_x_pct, ball_y_pct, caption, credit, license_url, source_url, "
            "player_image_id, is_published "
            "FROM spot_the_ball_puzzles "
            "WHERE ball_x_pct IS NOT NULL AND ball_y_pct IS NOT NULL "
            "ORDER BY puzzle_date ASC"
        )).all()
        log.info("found %d calibrated legacy rows", len(legacy))

        n_published = 0
        n_pool = 0
        for row in legacy:
            (
                puzzle_date, image_url, original_image_url, image_w, image_h,
                ball_x_pct, ball_y_pct, caption, credit, license_url, source_url,
                player_image_id, is_published,
            ) = row

            # is_inpainted maps to whether the image_url has been
            # swapped to the local processed file. Legacy is_published
            # flag tracks the same notion.
            is_inpainted = bool(is_published)

            new = SpotTheBallImage(
                set_id=None,
                position=None,
                image_url=image_url,
                original_image_url=original_image_url,
                image_w=image_w,
                image_h=image_h,
                ball_x_pct=ball_x_pct,
                ball_y_pct=ball_y_pct,
                caption=caption,
                credit=credit,
                license_url=license_url,
                source_url=source_url,
                source_player_image_id=player_image_id,
                is_inpainted=is_inpainted,
                inpaint_attempts=1 if is_inpainted else 0,
            )
            session.add(new)
            if is_inpainted:
                n_published += 1
            else:
                n_pool += 1
        session.commit()
        log.info("created %d SpotTheBallImage rows (%d inpainted, %d pool)",
                 n_published + n_pool, n_published, n_pool)

        log.info("bundling inpainted pool into sets…")
        sets = bundle_pool(session)
        log.info("created %d new SpotTheBallSet rows", len(sets))

        # Drop the legacy table. We have the migration committed at
        # this point so this is safe.
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE spot_the_ball_puzzles"))
        log.info("dropped spot_the_ball_puzzles")


if __name__ == "__main__":
    main()
