from datetime import date, datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class Tour(str, Enum):
    ATP = "atp"
    WTA = "wta"


class Player(SQLModel, table=True):
    __tablename__ = "players"

    id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(unique=True, index=True)
    full_name: str = Field(index=True)
    # Order-insensitive deduplication key — sorted-tokens lowercase form
    # of full_name. "Thiago Agustin Tirante" and "Agustin Tirante Thiago"
    # both produce "agustin-thiago-tirante" so the upsert path can spot
    # the same player even when sources reorder name parts.
    name_key: str | None = Field(default=None, index=True)
    first_name: str | None = None
    last_name: str | None = None
    tour: Tour = Field(index=True)
    country_code: str | None = Field(default=None, index=True, max_length=3)
    birth_date: date | None = None
    height_cm: int | None = None
    plays: str | None = None  # "right-handed, two-handed backhand"
    turned_pro: int | None = None

    # External IDs — keep all so we can cross-reference providers
    sackmann_id: str | None = Field(default=None, index=True)
    api_tennis_id: str | None = Field(default=None, index=True)

    # Cached snapshot (refreshed by jobs); detail page joins to Ranking for history
    current_rank: int | None = None
    career_high_rank: int | None = None

    image_url: str | None = None
    # Provenance of `image_url`: "wikipedia", "api-tennis", "manual", …
    # Drives whether we render a photo credit. api-tennis images are
    # editorial-feed thumbs (no credit needed in our use); Wikipedia
    # images are CC-BY / CC-BY-SA and require attribution.
    image_source: str | None = None
    # Photographer + license short-name, e.g. "Carine06 · CC BY-SA 2.0".
    # Pre-formatted for direct display.
    image_credit: str | None = None
    # Public URL of the license deed (e.g. https://creativecommons.org/
    # licenses/by-sa/2.0). Linked from the credit so anyone can verify.
    image_license_url: str | None = None
    # Landscape action-shot variant used as the profile-page background
    # band. Picked separately from `image_url` because Wikipedia
    # infobox photos are typically tight portrait crops — center-
    # cropping those into a 176px header band landed on armpits and
    # cleavage. Falls back to image_url at render time when null.
    hero_image_url: str | None = None
    bio: str | None = None

    # Wikidata-sourced — populated for top-N ranked players.
    wikidata_id: str | None = Field(default=None, index=True)
    wikipedia_url: str | None = None
    instagram_handle: str | None = None
    twitter_handle: str | None = None
    # Reserved for Phase 2 (paid API or scraper picks the latest post URL):
    instagram_latest_post_url: str | None = None
    socials_enriched_at: datetime | None = None
    bio_enriched_at: datetime | None = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
