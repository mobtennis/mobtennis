"""Name the Pro — multiple-choice trivia.

5 images per set; for each, the player sees the photo + 4 player
names (one correct, three distractors). Source pool is the same
PlayerImage table Spot the Ball uses, but the data shape is
different enough to warrant its own tables: no ball coords, no
inpainting, but each image carries its 3 distractor player slugs
and a denormalised display name.

Schema mirrors Spot the Ball's Set+Image split so the storage /
UI patterns line up:

  NameTheProSet     — one daily set (5 images)
  NameTheProImage   — one image in a set with its 4 options
"""

from datetime import date, datetime

from sqlmodel import Field, SQLModel


class NameTheProSet(SQLModel, table=True):
    __tablename__ = "ntp_sets"

    id: int | None = Field(default=None, primary_key=True)
    title: str | None = None
    publish_date: date = Field(index=True, unique=True)
    is_published: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class NameTheProImage(SQLModel, table=True):
    __tablename__ = "ntp_images"

    id: int | None = Field(default=None, primary_key=True)
    set_id: int | None = Field(
        default=None, foreign_key="ntp_sets.id", index=True,
    )
    position: int | None = None

    # Source photo — we don't need inpainting here, the ball can be
    # visible. Just the original PlayerImage.url.
    image_url: str
    caption: str  # player's full name (for the post-reveal label)

    # Four options + which is correct. Stored as JSON so the API can
    # hand the client a stable list it just renders as buttons.
    # Shape: [{"slug": "jannik-sinner", "full_name": "Jannik Sinner"}, ...]
    options_json: str
    correct_player_slug: str

    # Provenance + attribution.
    source_player_image_id: int | None = Field(
        default=None, foreign_key="player_images.id", index=True,
    )
    source_url: str | None = None  # Commons file page
    credit: str | None = None
    license_url: str | None = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
