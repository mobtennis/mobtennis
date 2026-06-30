"""One-time seed: copy the 5 hand-typed Call the Shot prototype items
out of web/lib/call-the-shot-data.ts into the cts_items table.

Idempotent: items keyed by (video_id, start_at_s, pause_at_s) — re-runs
skip rows that already exist with the same triple.

Usage:
  python -m scripts.seed_call_the_shot
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlmodel import Session, select

from app.db.session import engine, init_db
from app.models.call_the_shot import CallTheShotItem

log = logging.getLogger(__name__)


SEED: list[dict[str, Any]] = [
    {
        "video_id": "eRbTHj2KLro",
        "start_at_s": 15.0,
        "pause_at_s": 27.5,
        "caption": "Sinner vs Alcaraz · Wimbledon 2025 final",
        "options": ["Crosscourt volley", "Volley down the line", "Lob down the line", "Body shot"],
        "correct_index": 0,
        "source_url": "https://www.youtube.com/watch?v=eRbTHj2KLro",
    },
    {
        "video_id": "eRbTHj2KLro",
        "start_at_s": 35.0,
        "pause_at_s": 44.0,
        "caption": "Sinner vs Alcaraz · Wimbledon 2025 final",
        "options": ["Crosscourt drop shot", "Volley crosscourt", "Volley down the line", "Body shot"],
        "correct_index": 0,
        "source_url": "https://www.youtube.com/watch?v=eRbTHj2KLro",
    },
    {
        "video_id": "eRbTHj2KLro",
        "start_at_s": 95.0,
        "pause_at_s": 107.0,
        "caption": "Sinner vs Alcaraz · Wimbledon 2025 final",
        "options": ["Crosscourt", "Down the line", "Lob", "Body shot"],
        "correct_index": 0,
        "source_url": "https://www.youtube.com/watch?v=eRbTHj2KLro",
    },
    {
        "video_id": "eRbTHj2KLro",
        "start_at_s": 123.0,
        "pause_at_s": 133.0,
        "caption": "Sinner vs Alcaraz · Wimbledon 2025 final",
        "options": ["Crosscourt", "Down the line", "Lob", "Body shot"],
        "correct_index": 0,
        "source_url": "https://www.youtube.com/watch?v=eRbTHj2KLro",
    },
    {
        "video_id": "X4dVyRyY7TY",
        "start_at_s": 32.0,
        "pause_at_s": 37.0,
        "caption": "Świątek vs Anisimova · Wimbledon 2025 final",
        "options": ["Down the line", "Cross-court winner", "Body serve", "Drop shot"],
        "correct_index": 0,
        "source_url": "https://www.youtube.com/watch?v=X4dVyRyY7TY",
    },
]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    init_db()
    inserted = 0
    skipped = 0
    with Session(engine) as session:
        for item in SEED:
            existing = session.exec(
                select(CallTheShotItem).where(
                    CallTheShotItem.video_id == item["video_id"],
                    CallTheShotItem.start_at_s == item["start_at_s"],
                    CallTheShotItem.pause_at_s == item["pause_at_s"],
                )
            ).first()
            if existing:
                skipped += 1
                continue
            row = CallTheShotItem(
                video_id=item["video_id"],
                start_at_s=item["start_at_s"],
                pause_at_s=item["pause_at_s"],
                caption=item["caption"],
                options_json=json.dumps(item["options"]),
                correct_index=item["correct_index"],
                source_url=item.get("source_url"),
            )
            session.add(row)
            inserted += 1
        session.commit()
    log.info("seeded: inserted=%d skipped=%d", inserted, skipped)


if __name__ == "__main__":
    main()
