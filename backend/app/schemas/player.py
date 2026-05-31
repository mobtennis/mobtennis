from datetime import date

from pydantic import BaseModel

from app.models.player import Tour


class PlayerSummary(BaseModel):
    slug: str
    full_name: str
    tour: Tour
    country_code: str | None = None
    current_rank: int | None = None
    image_url: str | None = None


class PlayerDetail(PlayerSummary):
    first_name: str | None = None
    last_name: str | None = None
    birth_date: date | None = None
    height_cm: int | None = None
    plays: str | None = None
    turned_pro: int | None = None
    career_high_rank: int | None = None
    bio: str | None = None
    wikipedia_url: str | None = None
    instagram_handle: str | None = None
    twitter_handle: str | None = None
    instagram_latest_post_url: str | None = None  # Phase 2 field
    # Provenance + attribution for `image_url`. Set when the image
    # came from Wikipedia / Commons (CC-BY family licenses require
    # visible photo credit); null when no attribution is needed.
    image_source: str | None = None
    image_credit: str | None = None
    image_license_url: str | None = None


class PlayerImageView(BaseModel):
    """One photo of a player. Returned by /api/players/{slug}/images
    for the alternate-photos strip on the profile page."""
    id: int
    url: str
    source: str
    source_url: str | None = None
    credit: str | None = None
    license_url: str | None = None
    width: int | None = None
    height: int | None = None
    is_primary: bool
    is_hidden: bool
