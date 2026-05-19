"""Career snapshot for a single player.

Computed from the singles matches we have on record. Numbers are
bound by what's in our DB — Sackmann coverage starts in the 1970s
for ATP, similar for WTA. For a player whose career falls entirely
inside our window, these are the real career totals. For older
players, treat as "best case from available data."

Used by the player page to render an editorial-grade paragraph
under the bio.
"""

from pydantic import BaseModel


class SnapshotTitle(BaseModel):
    """A tournament victory — surfaced under 'titles' and used to
    populate the slam-results section."""
    year: int
    tournament_slug: str
    tournament_name: str
    tournament_tour: str
    category: str | None
    surface: str | None
    final_opponent_slug: str | None
    final_opponent_name: str | None
    final_score: str | None


class SurfaceRecord(BaseModel):
    surface: str
    wins: int
    losses: int


class PlayerSnapshot(BaseModel):
    slug: str
    full_name: str
    # Career totals (singles, from our DB — see module docstring).
    career_wins: int
    career_losses: int
    career_titles: int
    career_finals: int
    # Slam-specific subset (career_titles ⊇ slam_titles).
    slam_titles: int
    slam_finals: int
    best_slam: SnapshotTitle | None
    # Last 20 matches' record. Useful for "current form" line.
    recent_wins: int
    recent_losses: int
    # All-surface breakdown — usually 3 entries (hard / clay / grass).
    surfaces: list[SurfaceRecord]
    # Highest-ranked surface (most career wins, ignoring "unknown").
    best_surface: str | None
    # Most-played-opponent record. Useful for "biggest rival" line.
    biggest_rival_slug: str | None
    biggest_rival_name: str | None
    biggest_rival_record_wins: int
    biggest_rival_record_losses: int
    # The 5 most recent titles (newest first), for the "recent silverware" line.
    recent_titles: list[SnapshotTitle]
