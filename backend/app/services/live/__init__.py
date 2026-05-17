from app.config import settings
from app.services.live.api_tennis import ApiTennisProvider
from app.services.live.base import (
    LiveMatch,
    LiveScoresProvider,
    PlayerProfile,
    RankingEntry,
    TournamentMeta,
)
from app.services.live.noop import NoopProvider


def get_live_provider() -> LiveScoresProvider:
    """Factory — swap providers via LIVE_PROVIDER env var.

    Returns NoopProvider when no API key configured so dev/CI work
    without an external dependency.
    """
    if not settings.api_tennis_key:
        return NoopProvider()
    if settings.live_provider == "api_tennis":
        return ApiTennisProvider(
            api_key=settings.api_tennis_key,
            base_url=settings.api_tennis_base_url,
        )
    raise ValueError(f"Unknown live provider: {settings.live_provider}")


__all__ = [
    "LiveScoresProvider",
    "LiveMatch",
    "PlayerProfile",
    "RankingEntry",
    "TournamentMeta",
    "get_live_provider",
]
