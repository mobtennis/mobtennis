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
