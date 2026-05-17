from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class TournamentMeta:
    """Provider-agnostic tournament catalog entry."""

    external_id: str
    name: str
    tour: str           # "atp" | "wta"
    event_type: str     # raw upstream label, e.g. "Atp Singles", "Challenger Men Singles"
    surface: str | None = None  # "hard" | "clay" | "grass" | "carpet"
    is_doubles: bool = False


@dataclass
class PlayerProfile:
    """Provider-agnostic player profile, used for lazy enrichment."""

    external_id: str
    name: str
    country_name: str | None = None
    birth_date: date | None = None
    image_url: str | None = None


@dataclass
class RankingEntry:
    """Provider-agnostic ranking row."""

    rank: int
    points: int | None
    player_name: str
    player_external_id: str | None
    country_name: str | None  # full name from upstream; sync layer maps to ISO3
    movement: str | None  # "same" | "up" | "down" — provider-defined string
    tour: str  # "atp" | "wta"


@dataclass
class LiveMatch:
    """Provider-agnostic live match payload.

    Each provider maps its native shape to this. Persistence
    lives in `services/sync.py`, not in providers themselves —
    keeping the provider contract narrow.
    """

    provider_match_id: str
    tour: str  # "atp" | "wta"

    tournament_name: str
    tournament_external_id: str | None = None
    surface: str | None = None
    round: str | None = None

    player1_name: str | None = None
    player1_external_id: str | None = None
    player1_country: str | None = None

    player2_name: str | None = None
    player2_external_id: str | None = None
    player2_country: str | None = None

    score: str | None = None
    current_set: int | None = None
    current_game: str | None = None
    server: int | None = None  # 1 or 2

    status: str = "scheduled"  # scheduled | live | finished | retired | walkover | cancelled
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    winner: int | None = None  # 1 or 2

    is_doubles: bool = False
    best_of: int = 3

    raw: dict = field(default_factory=dict)


class LiveScoresProvider(ABC):
    """Pluggable live data source. Implementations: api-tennis, sportradar (future)."""

    name: str = "abstract"

    @abstractmethod
    async def fetch_live(self) -> list[LiveMatch]:
        """All currently-live matches across both tours."""

    @abstractmethod
    async def fetch_today(self) -> list[LiveMatch]:
        """Today's full schedule (live + scheduled + finished)."""

    @abstractmethod
    async def fetch_rankings(self, tour: str) -> list[RankingEntry]:
        """Current ATP or WTA rankings (top ~500). tour is 'atp' or 'wta'."""

    @abstractmethod
    async def fetch_player(self, external_id: str) -> PlayerProfile | None:
        """Single-player profile lookup. Returns None if not found."""

    @abstractmethod
    async def fetch_tournaments(self) -> list[TournamentMeta]:
        """Full tournament catalog (every brand the provider knows about)."""
