from datetime import date

from pydantic import BaseModel

from app.schemas.player import PlayerSummary


class RankingRow(BaseModel):
    rank: int
    points: int | None = None
    player: PlayerSummary


class RankingsResponse(BaseModel):
    tour: str
    week: date
    rows: list[RankingRow]
