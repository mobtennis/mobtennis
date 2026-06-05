"""Spot the Ball — daily 5-image round.

Schema split into two tables:

  SpotTheBallSet     — "one daily puzzle". Contains exactly 5 images
                       once bundled. Has a publish_date that gates
                       public visibility.
  SpotTheBallImage   — one tennis photo with one calibrated ball
                       position. Lives in a `pool` while set_id is
                       null; the bundler groups pool images into
                       sets when 5+ inpainted images exist with
                       enough player variety.

Bundling rule: no two images in the same set share a player. The
bundler tolerates a lopsided pool (many photos of one player) by
forming sets only when 5 distinct players are available; leftovers
stay in the pool until variety improves.

Local Replicate processing runs on SpotTheBallImage rows: download
original from Wikimedia, inpaint, save to web/public/spot-the-ball/
{id}.jpg, flag is_inpainted=True. Sets become public when all 5
images are inpainted AND the set has is_published=True AND today >=
publish_date.

SpotTheBallSkip table is unchanged — same semantics, lives on
PlayerImage IDs so the admin builder doesn't re-offer rejected
photos.
"""

from datetime import date, datetime

from sqlmodel import Field, SQLModel


class SpotTheBallSet(SQLModel, table=True):
    """One day's puzzle. Bundle of 5 SpotTheBallImage rows."""
    __tablename__ = "spot_the_ball_sets"

    id: int | None = Field(default=None, primary_key=True)

    # Optional human-readable label — used for themed sets and the
    # admin queue. Auto-set on bundle (e.g. "Round 7").
    title: str | None = None

    # Date this set becomes the "today" puzzle. Sets queue up
    # consecutively; bundler picks the next available date.
    publish_date: date = Field(index=True, unique=True)

    # Operator can hold a set back from public until they review
    # the inpaints (true by default since the bundler creates sets
    # only from already-inpainted images).
    is_published: bool = Field(default=True, index=True)

    created_at: datetime = Field(default_factory=datetime.utcnow)


class SpotTheBallImage(SQLModel, table=True):
    """One calibrated photo. In the pool while set_id is null;
    assigned to a set by the bundler."""
    __tablename__ = "spot_the_ball_images"

    id: int | None = Field(default=None, primary_key=True)

    # Membership in a set. Null = in pool, awaiting bundling.
    set_id: int | None = Field(
        default=None, foreign_key="spot_the_ball_sets.id", index=True,
    )
    # Position within the set (1..5). Null while in pool.
    position: int | None = None

    # Image data. image_url is the inpainted public version once
    # processed; original_image_url is the source on Wikimedia (used
    # for the reveal swap).
    image_url: str
    original_image_url: str | None = None
    image_w: int | None = None
    image_h: int | None = None

    # Ball position as percentages of image dimensions.
    ball_x_pct: float
    ball_y_pct: float

    # Display + attribution.
    caption: str
    credit: str | None = None
    license_url: str | None = None
    source_url: str | None = None  # Commons file page

    # Source provenance — links back to the PlayerImage row this
    # was built from. Used by the bundler to enforce the no-
    # duplicate-player constraint and by the rejection/retry loop
    # to mark sources as do-not-offer-again.
    source_player_image_id: int | None = Field(
        default=None, foreign_key="player_images.id", index=True,
    )

    # Inpaint lifecycle:
    #   is_inpainted = False  → image_url is the Wikimedia source
    #                           (ball still visible — must not go
    #                           public)
    #   is_inpainted = True   → image_url has been replaced with
    #                           the local /spot-the-ball/{id}.jpg
    #                           by the local Replicate processor.
    #
    # Sets only bundle from is_inpainted=True images.
    is_inpainted: bool = Field(default=False, index=True)

    # Attempt tracking for the reject-and-retry flow. inpaint_attempts
    # increments on each Replicate run; the processor uses it to bump
    # the mask radius on retries.
    inpaint_attempts: int = 0
    inpaint_rejected_at: datetime | None = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SpotTheBallSkip(SQLModel, table=True):
    """Admin skipped this image during the builder workflow — don't
    show it as a candidate again."""
    __tablename__ = "spot_the_ball_skips"

    id: int | None = Field(default=None, primary_key=True)
    player_image_id: int = Field(foreign_key="player_images.id", index=True, unique=True)
    skipped_at: datetime = Field(default_factory=datetime.utcnow)
