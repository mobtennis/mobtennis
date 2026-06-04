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


class CandidateView(BaseModel):
    """One PlayerImage offered to the admin builder. Includes
    everything the UI needs to render the photo + offer skip / use
    + auto-derive a caption when the admin schedules."""
    player_image_id: int
    image_url: str
    player_slug: str
    player_name: str
    suggested_caption: str
    credit: str | None = None
    license_url: str | None = None
    source_url: str | None = None  # Commons file page
    width: int | None = None
    height: int | None = None


class CandidateStats(BaseModel):
    """Sidebar counts on the builder page so the admin knows the
    state of the world."""
    candidates_remaining: int
    queued: int  # scheduled but not yet published (waiting on Replicate)
    published: int
    skipped: int


class ScheduleResponse(BaseModel):
    """What the admin sees after clicking the ball: which date the
    new puzzle was assigned to, plus the next candidate."""
    scheduled_date: date
    next_candidate: CandidateView | None = None
    stats: CandidateStats
