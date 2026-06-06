"""Public Name the Pro endpoints — daily multiple-choice trivia."""

from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.db.session import get_session
from app.models.name_the_pro import NameTheProImage, NameTheProSet
from app.schemas.name_the_pro import (
    NameTheProArchiveItem,
    NameTheProImageView,
    NameTheProOption,
    NameTheProSetView,
)

router = APIRouter(prefix="/api/name-the-pro", tags=["name-the-pro"])


def _published_filter():
    today = date.today()
    return (
        NameTheProSet.is_published == True,  # noqa: E712
        NameTheProSet.publish_date <= today,
    )


def _image_view(img: NameTheProImage) -> NameTheProImageView:
    options_raw = json.loads(img.options_json or "[]")
    options = [
        NameTheProOption(slug=o["slug"], full_name=o["full_name"])
        for o in options_raw
        if "slug" in o and "full_name" in o
    ]
    return NameTheProImageView(
        id=img.id,
        position=img.position,
        image_url=img.image_url,
        caption=img.caption,
        options=options,
        correct_player_slug=img.correct_player_slug,
        credit=img.credit,
        license_url=img.license_url,
        source_url=img.source_url,
    )


def _set_view(session: Session, s: NameTheProSet) -> NameTheProSetView:
    images = session.exec(
        select(NameTheProImage)
        .where(NameTheProImage.set_id == s.id)
        .order_by(NameTheProImage.position.asc())
    ).all()
    return NameTheProSetView(
        id=s.id,
        title=s.title,
        publish_date=s.publish_date,
        images=[_image_view(i) for i in images],
    )


@router.get("/today", response_model=NameTheProSetView)
def todays_set(session: Session = Depends(get_session)):
    today = date.today()
    s = session.exec(
        select(NameTheProSet).where(
            *_published_filter(),
            NameTheProSet.publish_date == today,
        )
    ).first()
    if not s:
        # Fallback to the most recent past set so the home page
        # never lands on a 404 just because today's slot is empty.
        s = session.exec(
            select(NameTheProSet)
            .where(*_published_filter())
            .order_by(NameTheProSet.publish_date.desc())
            .limit(1)
        ).first()
    if not s:
        raise HTTPException(404, "No sets available yet")
    return _set_view(session, s)


@router.get("/archive", response_model=list[NameTheProArchiveItem])
def archive(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    rows = session.exec(
        select(NameTheProSet)
        .where(*_published_filter())
        .order_by(NameTheProSet.publish_date.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    out: list[NameTheProArchiveItem] = []
    for s in rows:
        first_image = session.exec(
            select(NameTheProImage)
            .where(NameTheProImage.set_id == s.id)
            .order_by(NameTheProImage.position.asc())
            .limit(1)
        ).first()
        count = len(session.exec(
            select(NameTheProImage.id).where(NameTheProImage.set_id == s.id)
        ).all())
        out.append(
            NameTheProArchiveItem(
                id=s.id,
                title=s.title,
                publish_date=s.publish_date,
                image_count=count,
                cover_image_url=first_image.image_url if first_image else "",
            )
        )
    return out


@router.get("/{set_id}", response_model=NameTheProSetView)
def get_set(set_id: int, session: Session = Depends(get_session)):
    s = session.exec(
        select(NameTheProSet).where(
            NameTheProSet.id == set_id,
            *_published_filter(),
        )
    ).first()
    if not s:
        raise HTTPException(404, "Set not found")
    return _set_view(session, s)
