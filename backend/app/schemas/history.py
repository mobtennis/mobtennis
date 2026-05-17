from datetime import date

from pydantic import BaseModel

from app.schemas.player import PlayerSummary


class TournamentHistoryEntry(BaseModel):
    tournament_slug: str
    tournament_year: int
    tournament_name: str
    tournament_tour: str
    tournament_category: str | None = None
    tournament_surface: str | None = None
    tournament_image_url: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    result: str       # "W" | "F" | "SF" | "QF" | "R16" | ... | "—"
    is_winner: bool   # convenience for highlighting trophies


class TournamentChampion(BaseModel):
    year: int
    champion: PlayerSummary


class LastEdition(BaseModel):
    year: int
    champion: PlayerSummary
    runner_up: PlayerSummary | None = None
    final_score: str | None = None


class TournamentRecord(BaseModel):
    title: str            # "Most titles" / "Most appearances" / "Youngest champion"
    value: str            # "Novak Djokovic" / "Iga Swiatek"
    detail: str | None    # "7 titles" / "Age 19, 2020"
    player_slug: str | None = None
    image_url: str | None = None
    country_code: str | None = None


class TournamentStats(BaseModel):
    first_held: int | None = None
    total_editions: int = 0
    typical_month: int | None = None  # 1–12 for "When does it run?"
    draw_size: int | None = None
    prize_money: int | None = None
    surface: str | None = None
    indoor: bool = False


class TournamentOverview(BaseModel):
    last_edition: LastEdition | None = None
    records: list[TournamentRecord] = []
    stats: TournamentStats
