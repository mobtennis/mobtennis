"""Bundle pool images into sets of 5.

Pool = SpotTheBallImage rows where set_id IS NULL and the image has
been successfully inpainted (is_inpainted=True). The bundler walks
this pool and forms sets subject to:

  - Exactly 5 images per set
  - No two images in the same set share a player (uses
    SpotTheBallImage.source_player_image_id → PlayerImage.player_id)
  - Randomised order so consecutive calibrations from the same
    tournament don't all land in adjacent sets

When the pool can't make a complete set of 5 (fewer than 5 distinct
players represented), the leftover images stay in the pool until
more variety arrives.

Runs automatically when the queue page is opened. Idempotent — can
be re-invoked anytime; only creates new sets when there's enough
variety in the pool.
"""

from __future__ import annotations

import logging
import random
from collections import defaultdict
from datetime import date, timedelta

from sqlmodel import Session, select

from app.models.player_image import PlayerImage
from app.models.spot_the_ball import SpotTheBallImage, SpotTheBallSet

log = logging.getLogger(__name__)

IMAGES_PER_SET = 5


def _next_publish_date(session: Session) -> date:
    """The day after the latest scheduled set, or today if none."""
    last = session.exec(
        select(SpotTheBallSet.publish_date)
        .order_by(SpotTheBallSet.publish_date.desc())
        .limit(1)
    ).first()
    today = date.today()
    if not last:
        return today
    return max(last + timedelta(days=1), today)


def bundle_pool(session: Session, rng: random.Random | None = None) -> list[SpotTheBallSet]:
    """Form as many sets-of-5 as the current pool allows.

    The `rng` arg is for deterministic testing; production callers
    leave it None to use the module-level random instance.
    """
    if rng is None:
        rng = random.Random()

    # Fetch inpainted-and-unbundled images, joined to their player.
    rows = session.exec(
        select(SpotTheBallImage, PlayerImage.player_id)
        .join(PlayerImage, PlayerImage.id == SpotTheBallImage.source_player_image_id, isouter=True)
        .where(
            SpotTheBallImage.set_id.is_(None),
            SpotTheBallImage.is_inpainted == True,  # noqa: E712
            SpotTheBallImage.inpaint_rejected_at.is_(None),
        )
    ).all()

    # Group by player_id. Images without a known player (hand-seeded
    # legacy rows) get a sentinel "no-player" bucket — at most one of
    # those is allowed per set (treated as a distinct "player").
    by_player: dict[int | str, list[SpotTheBallImage]] = defaultdict(list)
    for img, player_id in rows:
        key = player_id if player_id is not None else f"none-{img.id}"
        by_player[key].append(img)

    sets_built: list[SpotTheBallSet] = []
    while len(by_player) >= IMAGES_PER_SET:
        # Random sample of 5 distinct players.
        chosen_players = rng.sample(list(by_player.keys()), IMAGES_PER_SET)
        # One random image per player.
        set_images: list[SpotTheBallImage] = []
        for pid in chosen_players:
            img = rng.choice(by_player[pid])
            set_images.append(img)

        new_set = SpotTheBallSet(
            publish_date=_next_publish_date(session),
            is_published=True,
        )
        session.add(new_set)
        session.flush()
        # Title defaults to "Round N" — N is the row id; useful in
        # the admin queue when nothing better is set.
        new_set.title = f"Round {new_set.id}"

        for position, img in enumerate(set_images, start=1):
            img.set_id = new_set.id
            img.position = position
            session.add(img)
            # Remove this specific image from its player bucket; drop
            # the bucket entirely if it's now empty.
            by_player[chosen_players[position - 1]].remove(img)
            if not by_player[chosen_players[position - 1]]:
                del by_player[chosen_players[position - 1]]

        session.commit()
        sets_built.append(new_set)
        log.info(
            "bundled set %d (publish_date=%s) with %d images",
            new_set.id, new_set.publish_date, len(set_images),
        )

    return sets_built
