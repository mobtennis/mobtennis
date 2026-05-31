"""Bulk-enrich Player rows with Wikipedia infobox images + license metadata.

Iterates players that have a wikipedia_url and either no image, or an
image whose source isn't "wikipedia" yet. Skip-flag --force re-runs
even for players already on Wikipedia images, useful if you fix the
enricher and want to refresh credit strings.

Polite by default: 500ms between API calls so we don't get rate-limited
out of the public MediaWiki endpoint. ~600 ranked players * ~2 API
calls * 500ms ≈ 10 minutes.

Usage:
  python -m scripts.enrich_player_images
  python -m scripts.enrich_player_images --only-ranked
  python -m scripts.enrich_player_images --force --limit 5
  python -m scripts.enrich_player_images --slug jannik-sinner
"""

from __future__ import annotations

import argparse
import logging
import time

from sqlmodel import Session, select

from app.db.session import engine, init_db
from app.models.player import Player
from app.services.players_image_enrich import build_client, enrich_one

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("enrich_player_images")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--only-ranked", action="store_true",
        help="Skip players with no current_rank. Default touches everyone.",
    )
    p.add_argument(
        "--force", action="store_true",
        help="Re-enrich even if image_source is already 'wikipedia'.",
    )
    p.add_argument(
        "--limit", type=int, default=None,
        help="Stop after N players (for spot-checks).",
    )
    p.add_argument(
        "--slug", default=None,
        help="Enrich exactly one player by slug. Bypasses all other filters.",
    )
    p.add_argument(
        "--sleep", type=float, default=0.5,
        help="Seconds between API calls. Polite default of 500ms.",
    )
    args = p.parse_args()

    init_db()
    client = build_client()
    n_seen = n_updated = n_skipped = 0
    with Session(engine) as s:
        if args.slug:
            rows = s.exec(select(Player).where(Player.slug == args.slug)).all()
        else:
            stmt = select(Player).where(Player.wikipedia_url.is_not(None))
            if args.only_ranked:
                stmt = stmt.where(Player.current_rank.is_not(None))
            if not args.force:
                # Only touch players who don't yet have a Wikipedia image.
                stmt = stmt.where(
                    (Player.image_source.is_(None))
                    | (Player.image_source != "wikipedia")
                )
            stmt = stmt.order_by(
                Player.current_rank.is_(None), Player.current_rank,
            )
            if args.limit:
                stmt = stmt.limit(args.limit)
            rows = s.exec(stmt).all()

        total = len(rows)
        n_new_images = 0
        log.info("Enriching %d players", total)
        for i, player in enumerate(rows, 1):
            n_seen += 1
            try:
                new_count = enrich_one(s, player, client)
            except Exception:
                log.exception("enrich failed for %s", player.slug)
                continue
            n_new_images += new_count
            # Always commit — even when no new rows were inserted, the
            # enricher may have refreshed metadata (credit, dimensions,
            # is_hero_eligible) on existing rows and re-synced the
            # primary/hero pointers on the player. Skipping the commit
            # silently discards those writes.
            s.commit()
            if new_count > 0:
                n_updated += 1
                log.info(
                    "[%d/%d] %s ← %d new images (primary: %s)",
                    i, total, player.slug, new_count,
                    (player.image_credit or "no-credit"),
                )
            else:
                n_skipped += 1
                log.debug("[%d/%d] %s: nothing new", i, total, player.slug)
            if i < total:
                time.sleep(args.sleep)

    client.close()
    log.info(
        "Done. seen=%d players_updated=%d new_images=%d nothing_new=%d",
        n_seen, n_updated, n_new_images, n_skipped,
    )


if __name__ == "__main__":
    main()
