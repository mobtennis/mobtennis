from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class FollowKind(str, Enum):
    PLAYER = "player"
    TOURNAMENT = "tournament"


class Follow(SQLModel, table=True):
    """Server-side follow record, keyed off the device's X-User-Token."""

    __tablename__ = "follows"

    id: int | None = Field(default=None, primary_key=True)
    user_token: str = Field(index=True)
    kind: FollowKind
    target_slug: str = Field(index=True)
    # Tournaments have non-unique slugs across tours (Rome ATP vs Rome WTA).
    # Players have globally-unique slugs, so target_tour is None for players.
    target_tour: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
