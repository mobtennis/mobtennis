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


class LiveRankingRow(RankingRow):
    """Augmented row for the live projection endpoint.

    `rank` / `points` are the official snapshot. `projected_rank` /
    `projected_points` are this-week-applied. `points_change` is the
    signed net (earned − defending).
    """
    projected_rank: int
    projected_points: int
    points_change: int


class LiveRankingsResponse(BaseModel):
    tour: str
    week: date  # snapshot week the projection is computed against
    rows: list[LiveRankingRow]
