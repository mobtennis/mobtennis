from pydantic import BaseModel

from app.schemas.match import MatchSummary
from app.schemas.player import PlayerSummary


class H2HSurfaceSplit(BaseModel):
    surface: str
    p1_wins: int
    p2_wins: int


class H2HResponse(BaseModel):
    player1: PlayerSummary
    player2: PlayerSummary
    p1_wins: int
    p2_wins: int
    matches: list[MatchSummary]
    surface_splits: list[H2HSurfaceSplit]
