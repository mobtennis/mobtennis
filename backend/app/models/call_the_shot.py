"""Call the Shot — predict-where-the-ball-goes game.

Mirrors the STB / NTP data shape: a parent CallTheShotSet (one per
publish day) groups 5 CallTheShotItem rows. Items can also exist
unassigned (set_id=NULL) — those live in the "pool" until the
bundler scoops them into the next available set.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlmodel import Field, SQLModel


class CallTheShotSet(SQLModel, table=True):
    __tablename__ = "cts_sets"

    id: int | None = Field(default=None, primary_key=True)
    title: str | None = None
    publish_date: date = Field(index=True, unique=True)
    is_published: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


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
    # Parent set + position. NULL when sitting in the pool waiting
    # for the bundler. Once bundled, items are pinned: re-running
    # the bundler doesn't shuffle them.
    set_id: int | None = Field(default=None, foreign_key="cts_sets.id", index=True)
    position: int | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
