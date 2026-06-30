from pydantic import BaseModel


class CallTheShotItemView(BaseModel):
    """Public read shape. options_json gets decoded to a list[str]."""
    id: int
    video_id: str
    start_at_s: float
    pause_at_s: float
    caption: str
    options: list[str]
    correct_index: int
    source_url: str | None = None


class CallTheShotItemCreate(BaseModel):
    """Admin write shape — used by the builder POST."""
    video_id: str
    start_at_s: float
    pause_at_s: float
    caption: str = ""
    options: list[str]  # validated server-side as exactly 4
    correct_index: int
    source_url: str | None = None


class CallTheShotItemUpdate(BaseModel):
    """Admin partial-update — any field optional."""
    video_id: str | None = None
    start_at_s: float | None = None
    pause_at_s: float | None = None
    caption: str | None = None
    options: list[str] | None = None
    correct_index: int | None = None
    source_url: str | None = None
    is_hidden: bool | None = None
