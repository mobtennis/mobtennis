from datetime import datetime

from sqlmodel import Field, SQLModel


class VideoItem(SQLModel, table=True):
    """A YouTube video ingested from one of the official tennis channels.

    Storage shape mirrors NewsItem so the two can be merged client-side
    into a single chronological feed. Video-specific fields:
      - `video_id`: the YouTube video id (11-char string), unique. Used
        for the embed URL `https://www.youtube.com/embed/{video_id}`.
      - `channel_name`: human-readable name of the source channel.

    Match-level association: `match_id` is reserved for a follow-up
    fuzzy-match pass that'll tie highlight videos to the specific Match
    row they cover, so match-detail pages can embed them.
    """

    __tablename__ = "video_items"

    id: int | None = Field(default=None, primary_key=True)
    source: str = Field(index=True)
    video_id: str = Field(unique=True, index=True)
    title: str
    summary: str | None = None
    thumbnail_url: str | None = None
    channel_name: str | None = None
    published_at: datetime = Field(index=True)

    # Keyword-tagged from the title — same approach as NewsItem.
    player_slugs: str | None = None
    tournament_slugs: str | None = None

    # Filled by a future fuzzy-match pass: nullable foreign key into
    # matches so we can embed the highlight on the match-detail page.
    match_id: int | None = Field(default=None, foreign_key="matches.id", index=True)

    # Portrait/landscape orientation, probed from the YouTube watch
    # page's og:video meta tags. NULL until probed. We treat portrait
    # videos (Shorts and vertical reels) differently in the UI: narrower
    # inline card + modal lightbox playback, vs the landscape inline-
    # iframe swap. NULL falls back to landscape rendering.
    is_portrait: bool | None = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
