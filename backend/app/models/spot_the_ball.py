"""Daily "Spot the Ball" puzzle — show a tennis action shot with the
ball removed, ask the user to click where it should be.

Inspired by the classic UK newspaper game. Tennis is unusually good
at it because the ball is small, the racket+body posture telegraphs
where it has to be, and frozen mid-stroke moments produce clean
puzzles.

Cadence: one puzzle per UTC day (puzzle_date unique). Old puzzles
stay playable indefinitely so late joiners get a full backlog (the
enclose.horse pattern). Scores live in client localStorage — no
account needed for v1; web stays anonymous per the identity policy.
"""

from datetime import date, datetime

from sqlmodel import Field, SQLModel


class SpotTheBallPuzzle(SQLModel, table=True):
    __tablename__ = "spot_the_ball_puzzles"

    id: int | None = Field(default=None, primary_key=True)

    # When this puzzle is the "daily" — also used as URL slug.
    puzzle_date: date = Field(index=True, unique=True)

    # Ball-removed image displayed during the puzzle. Local URL once
    # we've run the Flux-fill inpaint pipeline (web/public/spot-the-
    # ball/{date}.jpg via /spot-the-ball/{date}.jpg).
    image_url: str

    # Original photo with the ball still in it. Shown on the reveal
    # after the user locks in their guess — the "ohhh, THAT's where
    # it was" moment. Nullable for backwards compatibility with the
    # earliest seeded rows; the reveal falls back to the inpainted
    # image with a pin overlay when null.
    original_image_url: str | None = None

    # Native intrinsic dimensions of the image we're showing.
    # Nullable — the frontend reads `naturalWidth` / `naturalHeight`
    # from the loaded image element if these aren't seeded, so the
    # values are an optimisation (avoid layout shift on first paint),
    # not a correctness requirement.
    image_w: int | None = None
    image_h: int | None = None

    # True ball coordinates expressed as percentages of the image
    # dimensions (0.0–100.0). Storing as % means coords stay correct
    # at any rendered display size, including responsive resize on
    # phones vs desktop. Nullable for puzzles created via the seed
    # script before calibration — they're hidden from the public
    # endpoint until coords land.
    ball_x_pct: float | None = None
    ball_y_pct: float | None = None

    # Human-readable caption for the page header — "Kei Nishikori,
    # Wimbledon 2013" etc.
    caption: str

    # Photographer + license short-name, e.g. "Diliff · CC BY-SA 2.0".
    # Required for the CC-BY family on Commons — rendered under the
    # photo on the play page.
    credit: str | None = None
    license_url: str | None = None
    # Wikipedia / Commons page for the original. Linked from the
    # credit so curious players can see the source.
    source_url: str | None = None

    # Link back to the PlayerImage this puzzle was built from when it
    # came through the admin builder (vs. the v1 hand-seeded set,
    # which has no PlayerImage origin and leaves this null).
    player_image_id: int | None = Field(default=None, foreign_key="player_images.id", index=True)

    # Gated by the local Replicate processor: rows enter the queue
    # with is_published=False (image_url still points at the original
    # Wikimedia URL — the ball is visible, public must not see it).
    # Processor downloads, inpaints, writes to web/public, then sets
    # is_published=True. Public endpoints filter on this flag.
    is_published: bool = Field(default=False, index=True)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SpotTheBallSkip(SQLModel, table=True):
    """Admin skipped this image during the builder workflow — don't
    show it as a candidate again. Independent of PlayerImage.is_hidden
    (which has site-wide effects); skipping for Spot the Ball is a
    purely-game-side decision and doesn't influence other surfaces."""
    __tablename__ = "spot_the_ball_skips"

    id: int | None = Field(default=None, primary_key=True)
    player_image_id: int = Field(foreign_key="player_images.id", index=True, unique=True)
    skipped_at: datetime = Field(default_factory=datetime.utcnow)
