"""Public Spot the Ball endpoints — set-based model.

  - GET /today          → the set whose publish_date is today (or
                          the most recent past set if today's is
                          missing). 404 if no sets exist.
  - GET /archive        → published sets, newest first.
  - GET /{set_id}       → a specific set.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.db.session import get_session
from app.models.spot_the_ball import SpotTheBallImage, SpotTheBallSet
from app.schemas.spot_the_ball import (
    SpotTheBallImageView,
    SpotTheBallSetArchiveItem,
    SpotTheBallSetView,
)

router = APIRouter(prefix="/api/spot-the-ball", tags=["spot-the-ball"])


def _published_filter():
    today = date.today()
    return (
        SpotTheBallSet.is_published == True,  # noqa: E712
        SpotTheBallSet.publish_date <= today,
    )


def _set_view(session: Session, s: SpotTheBallSet) -> SpotTheBallSetView:
    images = session.exec(
        select(SpotTheBallImage)
        .where(SpotTheBallImage.set_id == s.id)
        .order_by(SpotTheBallImage.position.asc())
    ).all()
    return SpotTheBallSetView(
        id=s.id,
        title=s.title,
        publish_date=s.publish_date,
        images=[
            SpotTheBallImageView(
                id=i.id,
                position=i.position,
                image_url=i.image_url,
                original_image_url=i.original_image_url,
                image_w=i.image_w,
                image_h=i.image_h,
                ball_x_pct=i.ball_x_pct,
                ball_y_pct=i.ball_y_pct,
                caption=i.caption,
                credit=i.credit,
                license_url=i.license_url,
                source_url=i.source_url,
            )
            for i in images
        ],
    )


@router.get("/today", response_model=SpotTheBallSetView)
def todays_set(session: Session = Depends(get_session)):
    """The set published for today's date. If today has no scheduled
    set (rare; bundler ran short), fall back to the most recent past
    set so the home page isn't a dead-end."""
    today = date.today()
    s = session.exec(
        select(SpotTheBallSet).where(
            *_published_filter(),
            SpotTheBallSet.publish_date == today,
        )
    ).first()
    if not s:
        s = session.exec(
            select(SpotTheBallSet)
            .where(*_published_filter())
            .order_by(SpotTheBallSet.publish_date.desc())
            .limit(1)
        ).first()
    if not s:
        raise HTTPException(404, "No sets available yet")
    return _set_view(session, s)


@router.get("/archive", response_model=list[SpotTheBallSetArchiveItem])
def archive(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    rows = session.exec(
        select(SpotTheBallSet)
        .where(*_published_filter())
        .order_by(SpotTheBallSet.publish_date.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    out: list[SpotTheBallSetArchiveItem] = []
    for s in rows:
        first_image = session.exec(
            select(SpotTheBallImage)
            .where(SpotTheBallImage.set_id == s.id)
            .order_by(SpotTheBallImage.position.asc())
            .limit(1)
        ).first()
        count = len(session.exec(
            select(SpotTheBallImage.id).where(SpotTheBallImage.set_id == s.id)
        ).all())
        out.append(
            SpotTheBallSetArchiveItem(
                id=s.id,
                title=s.title,
                publish_date=s.publish_date,
                image_count=count,
                cover_image_url=first_image.image_url if first_image else "",
            )
        )
    return out


@router.get("/{set_id}", response_model=SpotTheBallSetView)
def get_set(set_id: int, session: Session = Depends(get_session)):
    s = session.exec(
        select(SpotTheBallSet).where(
            SpotTheBallSet.id == set_id,
            *_published_filter(),
        )
    ).first()
    if not s:
        raise HTTPException(404, "Set not found")
    return _set_view(session, s)
