from datetime import datetime

from sqlmodel import Field, SQLModel


class NewsItem(SQLModel, table=True):
    __tablename__ = "news_items"

    id: int | None = Field(default=None, primary_key=True)
    source: str = Field(index=True)  # "atptour", "wta", "tennis.com", "reuters"
    source_url: str = Field(unique=True, index=True)
    title: str
    summary: str | None = None
    image_url: str | None = None
    author: str | None = None
    published_at: datetime = Field(index=True)

    # Tag-style references for filtering on player/tournament pages
    player_slugs: str | None = None  # comma-separated, simple for v1
    tournament_slugs: str | None = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
