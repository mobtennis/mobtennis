"""Seed the Spot the Ball puzzle table with initial photos.

Each puzzle is keyed by `puzzle_date` (unique). The first seed batch
gets backdated so we have a small archive on day one of the game's
existence — late-joining players see a backlog to chew through, the
enclose.horse model.

Ball coordinates are LEFT NULL on purpose. After running this script
the puzzles aren't visible on the public archive yet — they get
calibrated by visiting `/play/spot-the-ball/{date}?calibrate=ADMIN_KEY`
on the live site and clicking the ball.

Idempotent: re-running won't duplicate rows (puzzle_date is unique;
inserts that conflict are skipped).
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlmodel import Session, select

from app.db.session import engine, init_db
from app.models.spot_the_ball import SpotTheBallPuzzle

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("seed_spot_the_ball")


# Initial seed batch. URLs sourced from Wikimedia Commons; credits
# match each file's Commons page. All CC-licensed.
SEEDS: list[dict] = [
    {
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Rich%C3%A8l_Hogenkamp_-_Masters_de_Madrid_2015_-_11.jpg/960px-Rich%C3%A8l_Hogenkamp_-_Masters_de_Madrid_2015_-_11.jpg",
        "caption": "Richèl Hogenkamp · Madrid Open 2015",
        "credit": "Tatiana · CC BY-SA 2.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/2.0/",
        "source_url": "https://commons.wikimedia.org/wiki/File:Rich%C3%A8l_Hogenkamp_-_Masters_de_Madrid_2015_-_11.jpg",
    },
    {
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b6/2017_US_Open_Tennis_-_Qualifying_Rounds_-_Viktoriya_Tomova_%28BUL%29_def._Polona_Hercog_%28SLO%29_%2836916572131%29.jpg/960px-2017_US_Open_Tennis_-_Qualifying_Rounds_-_Viktoriya_Tomova_%28BUL%29_def._Polona_Hercog_%28SLO%29_%2836916572131%29.jpg",
        "caption": "Viktoriya Tomova vs Polona Hercog · US Open Qualifying 2017",
        "credit": "Steven Pisano · CC BY 2.0",
        "license_url": "https://creativecommons.org/licenses/by/2.0/",
        "source_url": "https://commons.wikimedia.org/wiki/File:2017_US_Open_Tennis_-_Qualifying_Rounds_-_Viktoriya_Tomova_(BUL)_def._Polona_Hercog_(SLO)_(36916572131).jpg",
    },
    {
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/16/Kei_Nishikori_1%2C_Wimbledon_2013_-_Diliff.jpg/960px-Kei_Nishikori_1%2C_Wimbledon_2013_-_Diliff.jpg",
        "caption": "Kei Nishikori · Wimbledon 2013",
        "credit": "David Iliff (Diliff) · CC BY-SA 3.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/3.0/",
        "source_url": "https://commons.wikimedia.org/wiki/File:Kei_Nishikori_1,_Wimbledon_2013_-_Diliff.jpg",
    },
    {
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/10/Ana_Ivanovi%C4%87_-_Masters_de_Madrid_2015_-_01.jpg/960px-Ana_Ivanovi%C4%87_-_Masters_de_Madrid_2015_-_01.jpg",
        "caption": "Ana Ivanović · Madrid Open 2015",
        "credit": "Tatiana · CC BY-SA 2.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/2.0/",
        "source_url": "https://commons.wikimedia.org/wiki/File:Ana_Ivanovi%C4%87_-_Masters_de_Madrid_2015_-_01.jpg",
    },
    {
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6b/Javier_Mart%C3%AD_-_Masters_de_Madrid_2015_-_12.jpg/960px-Javier_Mart%C3%AD_-_Masters_de_Madrid_2015_-_12.jpg",
        "caption": "Javier Martí · Madrid Open 2015",
        "credit": "Tatiana · CC BY-SA 2.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/2.0/",
        "source_url": "https://commons.wikimedia.org/wiki/File:Javier_Mart%C3%AD_-_Masters_de_Madrid_2015_-_12.jpg",
    },
]


def main() -> None:
    init_db()
    today = date.today()
    with Session(engine) as session:
        inserted = 0
        skipped = 0
        # Backdate the batch so today's puzzle is the newest, and the
        # remainder sit in the archive ready to be played.
        for i, seed in enumerate(SEEDS):
            d = today - timedelta(days=i)
            existing = session.exec(
                select(SpotTheBallPuzzle).where(SpotTheBallPuzzle.puzzle_date == d)
            ).first()
            if existing:
                log.info("skipped %s (already seeded as %r)", d, existing.caption)
                skipped += 1
                continue
            row = SpotTheBallPuzzle(puzzle_date=d, **seed)
            session.add(row)
            inserted += 1
            log.info("seeded %s ← %r", d, seed["caption"])
        session.commit()
        log.info("done. inserted=%d skipped=%d", inserted, skipped)
        log.info("calibrate each by visiting "
                 "/play/spot-the-ball/<date>?calibrate=$ADMIN_KEY and "
                 "clicking the ball")


if __name__ == "__main__":
    main()
