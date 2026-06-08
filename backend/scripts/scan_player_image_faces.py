"""Scan PlayerImages for visible frontal faces.

Sets `face_detected` on each row so the Name the Pro picker can skip
photos where the player isn't identifiable (wide action shots, crowd
shots, back-of-head moments).

Idempotent: by default only scans rows where `face_detected IS NULL`.
Use --rescan to re-check rows that previously failed.

Usage:
  python -m scripts.scan_player_image_faces
  python -m scripts.scan_player_image_faces --limit 50
  python -m scripts.scan_player_image_faces --hero-eligible-only
  python -m scripts.scan_player_image_faces --rescan
"""

from __future__ import annotations

import argparse
import logging
import time

from sqlmodel import Session, select

from app.db.session import engine, init_db
from app.models.player_image import PlayerImage
from app.services.face_detect import detect_face_at_url

log = logging.getLogger(__name__)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=None,
                   help="Max rows to scan this run. Default: unlimited.")
    p.add_argument("--rescan", action="store_true",
                   help="Re-scan rows whose previous result was False.")
    p.add_argument("--hero-eligible-only", action="store_true",
                   help="Only scan rows already flagged is_hero_eligible.")
    p.add_argument("--sleep-ms", type=int, default=600,
                   help="Pause between fetches; polite to image hosts. "
                        "Wikimedia's bot detector 429s us at <300ms, "
                        "so default is conservative.")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    init_db()

    with Session(engine) as session:
        q = select(PlayerImage).where(PlayerImage.is_hidden == False)  # noqa: E712
        if args.hero_eligible_only:
            q = q.where(PlayerImage.is_hero_eligible == True)  # noqa: E712
        if args.rescan:
            q = q.where(
                (PlayerImage.face_detected.is_(None))
                | (PlayerImage.face_detected == False)  # noqa: E712
            )
        else:
            q = q.where(PlayerImage.face_detected.is_(None))
        q = q.order_by(PlayerImage.id)
        if args.limit:
            q = q.limit(args.limit)

        rows = session.exec(q).all()
        log.info("Scanning %d PlayerImage rows…", len(rows))

        positives = 0
        negatives = 0
        errors = 0
        for i, img in enumerate(rows, start=1):
            result = detect_face_at_url(img.url)
            if result.error:
                # Leave face_detected null so a future run can retry.
                errors += 1
                log.warning("id=%d  %s  →  %s", img.id, img.url, result.error)
            else:
                img.face_detected = result.detected
                session.add(img)
                if result.detected:
                    positives += 1
                    log.debug("id=%d  ✓ face %s", img.id, result.best)
                else:
                    negatives += 1
                    log.debug("id=%d  ✗ no face", img.id)
            if i % 25 == 0:
                session.commit()
                log.info("  …%d/%d  (+%d  -%d  err=%d)",
                         i, len(rows), positives, negatives, errors)
            if args.sleep_ms:
                time.sleep(args.sleep_ms / 1000.0)
        session.commit()
        log.info("Done. faces=%d  no-face=%d  errors=%d",
                 positives, negatives, errors)


if __name__ == "__main__":
    main()
