from datetime import datetime

from pydantic import BaseModel

from app.models.match import MatchStatus
from app.schemas.player import PlayerSummary


class PlayerStats(BaseModel):
    service_games_won: int = 0
    service_games_played: int = 0
    break_points_won: int = 0
    break_points_total: int = 0
    points_won: int = 0


class MatchStats(BaseModel):
    player1: PlayerStats
    player2: PlayerStats


class MatchSummary(BaseModel):
    id: int
    tournament_slug: str
    tournament_year: int
    tournament_name: str
    tournament_tour: str | None = None
    tournament_category: str | None = None
    tournament_surface: str | None = None
    round: str | None = None
    # Slot indicators (1 = player1, 2 = player2, None) — derived from the DB
    # foreign keys so clients don't need to know our internal player IDs.
    winner_slot: int | None = None
    server_slot: int | None = None
    court: str | None = None
    scheduled_at: datetime | None = None
    status: MatchStatus
    player1: PlayerSummary | None = None
    player2: PlayerSummary | None = None
    score: str | None = None
    current_set: int | None = None
    current_game: str | None = None
    server_player_id: int | None = None
    winner_id: int | None = None
    is_doubles: bool = False
    best_of: int = 3
    # Provider's match ID. For api-tennis this is roughly chronological,
    # which is NOT the same as draw position — clients should use
    # `bracket_position` for ordering.
    api_tennis_id: str | None = None
    # 0-indexed bracket slot within `round`. Populated by the Wikipedia
    # draw scraper (live top-tier events) or Sackmann ingest (completed
    # history); None means we don't yet have structural draw data and the
    # client should hide the bracket section.
    bracket_position: int | None = None
    player1_seed: int | None = None
    player2_seed: int | None = None


class MatchDetail(MatchSummary):
    started_at: datetime | None = None
    finished_at: datetime | None = None
    stats: MatchStats | None = None
