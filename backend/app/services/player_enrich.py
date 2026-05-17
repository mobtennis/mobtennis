"""Lazy player enrichment via the live provider.

Strategy: when someone visits a player page and we don't have an image,
call get_players once, persist what came back. Single call per player ever
(unless re-enrichment is forced).

`image_url` semantics:
  None  → never tried
  ""    → tried, no image available (don't retry)
  "..."  → real URL (cache forever)
"""

from __future__ import annotations

import logging

from sqlmodel import Session

from app.models.player import Player
from app.services.countries import name_to_iso3
from app.services.live import get_live_provider

log = logging.getLogger(__name__)


async def enrich_one(session: Session, player: Player) -> bool:
    """Returns True if any field updated. Tolerant of provider failure."""
    if not player.api_tennis_id:
        return False

    provider = get_live_provider()
    if provider.name == "noop":
        return False

    try:
        profile = await provider.fetch_player(player.api_tennis_id)
    except Exception:
        log.exception("enrich_one(%s) provider call failed", player.slug)
        return False

    if profile is None:
        # Mark we tried so we don't keep hitting the API for missing players.
        player.image_url = ""
        session.add(player)
        session.commit()
        return False

    changed = False
    if profile.image_url and player.image_url != profile.image_url:
        player.image_url = profile.image_url
        changed = True
    elif player.image_url is None:
        player.image_url = ""
        changed = True

    if profile.country_name and not player.country_code:
        iso3 = name_to_iso3(profile.country_name)
        if iso3:
            player.country_code = iso3
            changed = True

    if profile.birth_date and not player.birth_date:
        player.birth_date = profile.birth_date
        changed = True

    if changed:
        session.add(player)
        session.commit()
    return changed
