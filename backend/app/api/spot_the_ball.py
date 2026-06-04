"""Public endpoints for the Spot the Ball daily game.

Three reads, no writes from the public surface:
  - GET /today           — the puzzle for today (UTC). 404 if none seeded.
  - GET /archive         — paginated backlog (newest first), without coords.
  - GET /{date}          — a specific dated puzzle.

Calibration (admin-only, sets ball coords) lives on the admin router
because it needs the ADMIN_KEY gate.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.db.session import get_session
from app.models.spot_the_ball import SpotTheBallPuzzle
from app.schemas.spot_the_ball import SpotTheBallArchiveItem, SpotTheBallPuzzleView

router = APIRouter(prefix="/api/spot-the-ball", tags=["spot-the-ball"])


def _view(row: SpotTheBallPuzzle) -> SpotTheBallPuzzleView:
    return SpotTheBallPuzzleView(
        puzzle_date=row.puzzle_date,
        image_url=row.image_url,
        original_image_url=row.original_image_url,
        image_w=row.image_w,
        image_h=row.image_h,
        # Public endpoint only returns puzzles with coords calibrated;
        # _ball_*_pct cannot be null here. `or 50.0` is paranoia.
        ball_x_pct=row.ball_x_pct or 50.0,
        ball_y_pct=row.ball_y_pct or 50.0,
        caption=row.caption,
        credit=row.credit,
        license_url=row.license_url,
        source_url=row.source_url,
    )


def _calibrated_filter():
    """Puzzles are hidden until ball_x_pct + ball_y_pct land. Lets us
    seed photos in advance without exposing un-calibrated rows on the
    public archive."""
    return (
        SpotTheBallPuzzle.ball_x_pct.is_not(None),
        SpotTheBallPuzzle.ball_y_pct.is_not(None),
    )


@router.get("/today", response_model=SpotTheBallPuzzleView)
def todays_puzzle(session: Session = Depends(get_session)):
    today = date.today()
    row = session.exec(
        select(SpotTheBallPuzzle)
        .where(
            SpotTheBallPuzzle.puzzle_date == today,
            *_calibrated_filter(),
        )
    ).first()
    if not row:
        # Fallback: most recent calibrated puzzle on or before today.
        # Means if we ever miss a day, today's visit still lands on
        # something playable rather than a 404 dead-end.
        row = session.exec(
            select(SpotTheBallPuzzle)
            .where(
                SpotTheBallPuzzle.puzzle_date <= today,
                *_calibrated_filter(),
            )
            .order_by(SpotTheBallPuzzle.puzzle_date.desc())
            .limit(1)
        ).first()
    if not row:
        raise HTTPException(404, "No puzzles available yet")
    return _view(row)


@router.get("/archive", response_model=list[SpotTheBallArchiveItem])
def archive(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    """All calibrated puzzles, newest first. The backlog the player
    catches up on if they discover the game late."""
    rows = session.exec(
        select(SpotTheBallPuzzle)
        .where(*_calibrated_filter())
        .order_by(SpotTheBallPuzzle.puzzle_date.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return [
        SpotTheBallArchiveItem(
            puzzle_date=r.puzzle_date,
            caption=r.caption,
            image_url=r.image_url,
        )
        for r in rows
    ]


@router.get("/{puzzle_date}", response_model=SpotTheBallPuzzleView)
def get_puzzle(
    puzzle_date: date,
    session: Session = Depends(get_session),
):
    row = session.exec(
        select(SpotTheBallPuzzle).where(
            SpotTheBallPuzzle.puzzle_date == puzzle_date,
            *_calibrated_filter(),
        )
    ).first()
    if not row:
        raise HTTPException(404, "Puzzle not found")
    return _view(row)
