from datetime import datetime

from pydantic import BaseModel


class VideoItemSummary(BaseModel):
    id: int
    source: str
    video_id: str
    title: str
    summary: str | None
    thumbnail_url: str | None
    channel_name: str | None
    published_at: datetime
    player_slugs: list[str]
    tournament_slugs: list[str]
    match_id: int | None = None
    is_portrait: bool | None = None
