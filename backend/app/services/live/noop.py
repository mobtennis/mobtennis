from app.services.live.base import (
    LiveMatch,
    LiveScoresProvider,
    PlayerProfile,
    RankingEntry,
    TournamentMeta,
)


class NoopProvider(LiveScoresProvider):
    """Used when no live API key is configured. App still runs on Sackmann + RSS."""

    name = "noop"

    async def fetch_live(self) -> list[LiveMatch]:
        return []

    async def fetch_today(self) -> list[LiveMatch]:
        return []

    async def fetch_rankings(self, tour: str) -> list[RankingEntry]:
        return []

    async def fetch_player(self, external_id: str) -> PlayerProfile | None:
        return None

    async def fetch_tournaments(self) -> list[TournamentMeta]:
        return []
