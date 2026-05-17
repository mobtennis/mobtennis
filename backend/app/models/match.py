from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class Surface(str, Enum):
    HARD = "hard"
    CLAY = "clay"
    GRASS = "grass"
    CARPET = "carpet"


class MatchStatus(str, Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    # Play has started but is paused (rain delay, lighting, medical
    # timeout exceeding the live feed's "still playing" tolerance).
    # api-tennis sends `event_status='Interrupted'` with
    # `event_live='0'`; the in-progress score persists in their
    # `scores` array. We surface these alongside LIVE matches with a
    # "Suspended" badge so they don't drop out of the live view.
    SUSPENDED = "suspended"
    FINISHED = "finished"
    RETIRED = "retired"
    WALKOVER = "walkover"
    CANCELLED = "cancelled"
    POSTPONED = "postponed"


class Match(SQLModel, table=True):
    __tablename__ = "matches"

    id: int | None = Field(default=None, primary_key=True)
    tournament_id: int = Field(foreign_key="tournaments.id", index=True)

    round: str | None = Field(default=None, index=True)  # "F", "SF", "QF", "R16", "R32"...
    court: str | None = None
    scheduled_at: datetime | None = Field(default=None, index=True)
    started_at: datetime | None = None
    finished_at: datetime | None = None

    status: MatchStatus = Field(default=MatchStatus.SCHEDULED, index=True)

    player1_id: int | None = Field(default=None, foreign_key="players.id", index=True)
    player2_id: int | None = Field(default=None, foreign_key="players.id", index=True)

    # Set scores stored as compact strings: "6-4 7-6(5) 3-6 6-3"
    score: str | None = None
    # Live state: current set, current game points (e.g. "30-40", "AD-40")
    current_set: int | None = None
    current_game: str | None = None
    server_player_id: int | None = None

    winner_id: int | None = Field(default=None, foreign_key="players.id")
    is_doubles: bool = False
    best_of: int = 3  # 3 or 5

    api_tennis_id: str | None = Field(default=None, index=True, unique=True)
    sackmann_id: str | None = Field(default=None, index=True)

    # Bracket structure. Populated by the Wikipedia draw scraper (for live
    # top-tier events) and Sackmann ingest (for completed history). 0-indexed
    # within the round: an R128 match at bracket_position=K matches slots 2K
    # and 2K+1; the winner advances to R64 bracket_position=K÷2; etc.
    bracket_position: int | None = Field(default=None, index=True)
    # Per-edition seed for each player. NULL means unseeded/qualifier/WC.
    # Carried separately from the Player row because seeds are per-tournament.
    player1_seed: int | None = None
    player2_seed: int | None = None

    # JSON-encoded MatchStats — derived from provider's pointbypoint array.
    # Refreshed on every poll; stays populated after the match finishes so
    # historical match detail pages can show the same stats panel.
    stats_json: str | None = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
