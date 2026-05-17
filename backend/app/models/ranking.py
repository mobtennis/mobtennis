from datetime import date, datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.player import Tour


class Ranking(SQLModel, table=True):
    __tablename__ = "rankings"
    __table_args__ = (
        # One snapshot per (player, tour, week). Without this, merging
        # duplicate Player rows could leave behind multiple Ranking rows
        # all pointing at the canonical player_id with the same week.
        UniqueConstraint("player_id", "tour", "week", name="uq_rankings_player_tour_week"),
        {"sqlite_autoincrement": True},
    )

    id: int | None = Field(default=None, primary_key=True)
    player_id: int = Field(foreign_key="players.id", index=True)
    tour: Tour = Field(index=True)
    week: date = Field(index=True)
    rank: int = Field(index=True)
    points: int | None = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
