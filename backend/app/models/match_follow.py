from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class MatchFollowGranularity(str, Enum):
    # Match start/end, set end, break of serve, tiebreak start.
    KEY_MOMENTS = "key_moments"
    # Above + every game completion.
    EVERY_GAME = "every_game"


class MatchFollow(SQLModel, table=True):
    """Transient follow keyed off device token. Auto-purged when the match
    transitions to a terminal status (finished/retired/walkover/cancelled)."""

    __tablename__ = "match_follows"

    id: int | None = Field(default=None, primary_key=True)
    user_token: str = Field(index=True)
    match_id: int = Field(foreign_key="matches.id", index=True)
    granularity: MatchFollowGranularity = Field(default=MatchFollowGranularity.KEY_MOMENTS)
    created_at: datetime = Field(default_factory=datetime.utcnow)
