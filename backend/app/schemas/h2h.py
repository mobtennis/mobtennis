from pydantic import BaseModel

from app.schemas.match import MatchSummary
from app.schemas.player import PlayerSummary


class H2HSurfaceSplit(BaseModel):
    surface: str
    p1_wins: int
    p2_wins: int


class H2HMeeting(BaseModel):
    """Compact pointer to one specific match. Used by the H2H summary
    block for 'first meeting' / 'last meeting' callouts so the page
    can render a sentence without re-fetching the Match row."""
    year: int
    tournament_name: str | None
    tournament_slug: str | None
    tournament_tour: str | None
    round: str | None
    winner_slug: str | None      # the player who won (slug, not full name)
    score: str | None


class H2HSummary(BaseModel):
    """Editorial-grade summary computed across the full match history,
    not just the most recent 20. Drives the prose paragraph on the
    H2H page."""
    total_meetings: int
    finals_meetings: int             # how many times they played a final
    span_years: int | None           # years between first and most recent
    first_meeting: H2HMeeting | None
    last_meeting: H2HMeeting | None
    # Active streak: which slug is currently winning the H2H, and by how
    # many in a row. Null when there are no meetings yet.
    current_streak_slug: str | None
    current_streak_count: int


class H2HResponse(BaseModel):
    player1: PlayerSummary
    player2: PlayerSummary
    p1_wins: int
    p2_wins: int
    matches: list[MatchSummary]
    surface_splits: list[H2HSurfaceSplit]
    summary: H2HSummary | None = None
