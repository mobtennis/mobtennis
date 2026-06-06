from datetime import date

from pydantic import BaseModel


class NameTheProOption(BaseModel):
    """One of the 4 buttons rendered under an image."""
    slug: str
    full_name: str


class NameTheProImageView(BaseModel):
    """One image in a Name the Pro set. The frontend renders the
    photo + the 4 options as buttons and scores against
    `correct_player_slug` when the user picks one."""
    id: int
    position: int | None = None
    image_url: str
    caption: str
    options: list[NameTheProOption]
    correct_player_slug: str
    credit: str | None = None
    license_url: str | None = None
    source_url: str | None = None


class NameTheProSetView(BaseModel):
    id: int
    title: str | None = None
    publish_date: date
    images: list[NameTheProImageView]


class NameTheProArchiveItem(BaseModel):
    id: int
    title: str | None = None
    publish_date: date
    image_count: int
    cover_image_url: str
