from datetime import date

from pydantic import BaseModel


class SpotTheBallImageView(BaseModel):
    """One of the 5 photos in a set. Returned to the player along
    with the set so the round-mode UI can render them in sequence."""
    id: int
    position: int | None = None
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


class SpotTheBallSetView(BaseModel):
    """Daily set — title + 5 images."""
    id: int
    title: str | None = None
    publish_date: date
    images: list[SpotTheBallImageView]


class SpotTheBallSetArchiveItem(BaseModel):
    """Lightweight row for the archive list."""
    id: int
    title: str | None = None
    publish_date: date
    image_count: int
    cover_image_url: str  # the first image's url for thumbnail


class CandidateView(BaseModel):
    """One PlayerImage offered to the admin builder."""
    player_image_id: int
    image_url: str
    player_slug: str
    player_name: str
    suggested_caption: str
    credit: str | None = None
    license_url: str | None = None
    source_url: str | None = None
    width: int | None = None
    height: int | None = None


class CandidateStats(BaseModel):
    candidates_remaining: int
    pool: int        # calibrated images awaiting bundling
    sets_published: int
    skipped: int


class ScheduleResponse(BaseModel):
    """Reply to a calibration POST — confirms acceptance + serves next."""
    image_id: int
    next_candidate: CandidateView | None = None
    stats: CandidateStats


class QueueImageItem(BaseModel):
    """Single image in the admin queue listing. Shows pool images
    awaiting bundling and bundled images grouped by set."""
    id: int
    set_id: int | None
    position: int | None
    image_url: str
    original_image_url: str | None
    caption: str
    is_inpainted: bool
    inpaint_attempts: int
    inpaint_rejected_at: str | None = None
    ball_x_pct: float
    ball_y_pct: float


class QueueResponse(BaseModel):
    """Admin queue view: pool first, then published sets newest-first."""
    pool: list[QueueImageItem]
    sets: list[SpotTheBallSetView]
    # Flat list of every image (set or pool) that still needs an
    # inpaint pass — pool images that haven't been processed AND
    # in-set images the admin rejected. The local processor consumes
    # this so a "reject" on an already-bundled image gets fixed on
    # the next run.
    images_needing_inpaint: list[QueueImageItem]
