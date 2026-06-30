"""Call the Shot — predict-where-the-ball-goes game.

One row per playable item: a YouTube clip + a pause point + 4 options
(stored as JSON since SQLite has no array type) + the correct index.
No daily-set concept yet — items are played in one flat list,
auto-sorted by (video_id, start_at_s) on the frontend.

If/when we need bundled daily rounds (matching STB/NTP), we'd add a
cts_sets table + a set_id FK here. For now flat list keeps the
content pipeline simple.
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel


class CallTheShotItem(SQLModel, table=True):
    __tablename__ = "cts_items"

    id: int | None = Field(default=None, primary_key=True)
    # YouTube video ID (11 chars, e.g. "eRbTHj2KLro"). Never the full URL.
    video_id: str = Field(index=True)
    # Where to seek before play. Fractional seconds.
    start_at_s: float
    # Where to pause for the prediction. Fractional seconds.
    pause_at_s: float
    caption: str = ""
    # JSON-encoded list of exactly 4 strings.
    options_json: str
    # 0..3 into the options array.
    correct_index: int
    # Optional human-friendly link back to the video.
    source_url: str | None = None
    # Hide from the public list without deleting — useful if the
    # source video gets taken down and we want to keep the row for
    # audit. Default visible.
    is_hidden: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
