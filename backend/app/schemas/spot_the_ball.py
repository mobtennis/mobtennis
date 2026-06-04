from datetime import date

from pydantic import BaseModel


class SpotTheBallPuzzleView(BaseModel):
    """Public-facing puzzle payload. Ball coordinates are intentionally
    INCLUDED — the client needs them to compute distance after the user
    locks in a guess. (We're not preventing inspect-element cheating
    on v1; the social value is in the personal accuracy stat, not in
    a global leaderboard. If we add leaderboards later we'll move the
    distance computation server-side.)
    """
    puzzle_date: date
    image_url: str
    original_image_url: str | None = None
    image_w: int | None = None
    image_h: int | None = None
    ball_x_pct: float
    ball_y_pct: float
    caption: str
    credit: str | None = None
    license_url: str | None = None
    source_url: str | None = None


class SpotTheBallArchiveItem(BaseModel):
    """Lightweight row for the archive list — no coords, no full caption
    detail. Used to render the backlog index."""
    puzzle_date: date
    caption: str
    image_url: str
