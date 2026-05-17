from datetime import date

from pydantic import BaseModel

from app.models.player import Tour
from app.models.tournament import TournamentCategory


class TournamentSummary(BaseModel):
    slug: str
    year: int
    name: str
    tour: Tour
    category: TournamentCategory
    surface: str | None = None
    indoor: bool = False
    city: str | None = None
    country_code: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    draw_size: int | None = None
    image_url: str | None = None  # Wikipedia thumbnail


class TournamentDetail(TournamentSummary):
    prize_money: int | None = None
    description: str | None = None
    wikipedia_url: str | None = None
    # All tours that have this (slug, year) brand — drives the ATP/WTA pill
    # switcher on the detail page header.
    available_tours: list[str] = []
