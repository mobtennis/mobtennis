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
