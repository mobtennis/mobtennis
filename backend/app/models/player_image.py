"""One PlayerImage row per discovered photo of a player.

We collect rather than overwrite so:
  - Wikipedia edits that swap to a worse photo don't lose us the
    previous good one.
  - Admins can hide a bad shot (e.g. shadowed face, blurry) without
    deleting the row — re-runs of the enricher won't re-introduce it
    because `is_hidden` is sticky.
  - The player profile page can show a small "more photos" strip
    once a player has ≥4 unhidden images.

Player.image_url is kept as a denormalised pointer to whichever
PlayerImage is currently `is_primary=True`. This is the hot path
(every match card, every ranking row, every avatar) — running a
joined query for every render would be needlessly expensive when
the primary changes monthly at most.
"""

from datetime import datetime

from sqlmodel import Field, SQLModel


class PlayerImage(SQLModel, table=True):
    __tablename__ = "player_images"

    id: int | None = Field(default=None, primary_key=True)
    player_id: int = Field(foreign_key="players.id", index=True)

    # The publicly-reachable image URL we render. For Wikipedia images
    # this is the upload.wikimedia.org/wikipedia/commons/… file URL.
    url: str = Field(index=True, unique=True)

    # Provenance.
    #   "wikipedia"   — fetched from a Wikipedia article infobox or body
    #   "commons"     — from a Wikimedia Commons category
    #   "api-tennis"  — editorial-feed thumb from the live-data provider
    #   "manual"      — set by an admin
    source: str

    # URL on the upstream that points back at this image's context —
    # the Wikipedia page, the Commons file page, etc. Useful for
    # admins reviewing why an image exists.
    source_url: str | None = None

    # Pre-formatted attribution string, e.g. "Carine06 · CC BY-SA 2.0".
    # Rendered under the photo on the player profile page.
    credit: str | None = None
    license_url: str | None = None

    # Dimensions when we know them (Wikipedia returns these in
    # extmetadata). Lets us prefer landscape-cropped photos for
    # landscape contexts like the digest video.
    width: int | None = None
    height: int | None = None

    # Display flags.
    #   is_primary  — this is the one shown by default. Exactly one
    #                 PlayerImage per player should have this true;
    #                 maintained by the enricher / admin endpoint.
    #   is_hidden   — admin opted out of showing this image (bad
    #                 framing, wrong player, whatever). Sticky across
    #                 re-runs of the enricher — never auto-resurrected.
    is_primary: bool = Field(default=False, index=True)
    is_hidden: bool = False
    # Hero-band candidate: landscape-aspect action shots that work in
    # the 176px-tall background band on the player profile page.
    # Portrait headshots (the typical infobox lead) get eligible=False
    # so the hero picker doesn't choose one and crop to a chest area.
    is_hero_eligible: bool = False
    # The chosen hero for this player. Exactly one row per player
    # carries this flag; null hero_image_url on Player when none of
    # the player's images are eligible (we'd rather no hero band than
    # an awkward crop).
    is_hero: bool = Field(default=False, index=True)

    discovered_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
