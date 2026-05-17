from datetime import datetime

from pydantic import BaseModel


class NewsItemSummary(BaseModel):
    id: int
    source: str
    source_url: str
    title: str
    summary: str | None = None
    image_url: str | None = None
    author: str | None = None
    published_at: datetime
    player_slugs: list[str] = []
    tournament_slugs: list[str] = []
