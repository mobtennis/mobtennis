from datetime import date, datetime
from enum import Enum

from sqlmodel import Field, SQLModel

from app.models.player import Tour


class TournamentCategory(str, Enum):
    GRAND_SLAM = "grand_slam"
    ATP_1000 = "atp_1000"
    ATP_500 = "atp_500"
    ATP_250 = "atp_250"
    ATP_FINALS = "atp_finals"
    WTA_1000 = "wta_1000"
    WTA_500 = "wta_500"
    WTA_250 = "wta_250"
    WTA_FINALS = "wta_finals"
    CHALLENGER = "challenger"
    ITF = "itf"
    DAVIS_CUP = "davis_cup"
    BJK_CUP = "bjk_cup"
    OTHER = "other"


class Tournament(SQLModel, table=True):
    __tablename__ = "tournaments"

    id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(index=True)  # e.g. "wimbledon"
    year: int = Field(index=True)
    name: str
    tour: Tour = Field(index=True)
    category: TournamentCategory = Field(index=True)
    surface: str | None = Field(default=None, index=True)  # hard, clay, grass, carpet
    indoor: bool = False
    city: str | None = None
    country_code: str | None = Field(default=None, max_length=3)
    start_date: date | None = None
    end_date: date | None = None
    draw_size: int | None = None
    prize_money: int | None = None  # USD

    sackmann_id: str | None = None
    api_tennis_id: str | None = None

    # Wikipedia-sourced enrichment
    description: str | None = None     # short blurb (lead paragraph, trimmed)
    image_url: str | None = None       # venue / trophy photo
    wikipedia_url: str | None = None
    enriched_at: datetime | None = None  # null = never tried; set = tried (don't retry)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
