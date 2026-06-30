"""Public Call the Shot endpoints — daily 5-item rounds."""

from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.db.session import get_session
from app.models.call_the_shot import CallTheShotItem, CallTheShotSet
from app.schemas.call_the_shot import (
    CallTheShotArchiveItem,
    CallTheShotItemView,
    CallTheShotSetView,
)

router = APIRouter(prefix="/api/call-the-shot", tags=["call-the-shot"])


def _published_filter():
    today = date.today()
    return (
        CallTheShotSet.is_published == True,  # noqa: E712
        CallTheShotSet.publish_date <= today,
    )


def _item_view(row: CallTheShotItem) -> CallTheShotItemView:
    try:
        options = json.loads(row.options_json or "[]")
    except json.JSONDecodeError:
        options = []
    return CallTheShotItemView(
        id=row.id,
        position=row.position,
        video_id=row.video_id,
        start_at_s=row.start_at_s,
        pause_at_s=row.pause_at_s,
        caption=row.caption,
        options=options,
        correct_index=row.correct_index,
        source_url=row.source_url,
    )


def _set_view(session: Session, s: CallTheShotSet) -> CallTheShotSetView:
    items = session.exec(
        select(CallTheShotItem)
        .where(
            CallTheShotItem.set_id == s.id,
            CallTheShotItem.is_hidden == False,  # noqa: E712
        )
        .order_by(CallTheShotItem.position.asc())
    ).all()
    return CallTheShotSetView(
        id=s.id,
        title=s.title,
        publish_date=s.publish_date,
        items=[_item_view(it) for it in items],
    )


@router.get("/today", response_model=CallTheShotSetView)
def todays_set(session: Session = Depends(get_session)):
    today = date.today()
    s = session.exec(
        select(CallTheShotSet).where(
            *_published_filter(),
            CallTheShotSet.publish_date == today,
        )
    ).first()
    if not s:
        # Fallback to the most recent past set — keeps /play/call-the-shot
        # from 404ing when today's set hasn't been bundled yet.
        s = session.exec(
            select(CallTheShotSet)
            .where(*_published_filter())
            .order_by(CallTheShotSet.publish_date.desc())
            .limit(1)
        ).first()
    if not s:
        raise HTTPException(404, "No sets available yet")
    return _set_view(session, s)


@router.get("/archive", response_model=list[CallTheShotArchiveItem])
def archive(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    rows = session.exec(
        select(CallTheShotSet)
        .where(*_published_filter())
        .order_by(CallTheShotSet.publish_date.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    out: list[CallTheShotArchiveItem] = []
    for s in rows:
        count = len(session.exec(
            select(CallTheShotItem.id).where(CallTheShotItem.set_id == s.id)
        ).all())
        out.append(
            CallTheShotArchiveItem(
                id=s.id,
                title=s.title,
                publish_date=s.publish_date,
                item_count=count,
            )
        )
    return out


@router.get("/{set_id}", response_model=CallTheShotSetView)
def get_set(set_id: int, session: Session = Depends(get_session)):
    s = session.exec(
        select(CallTheShotSet).where(
            CallTheShotSet.id == set_id,
            *_published_filter(),
        )
    ).first()
    if not s:
        raise HTTPException(404, "Set not found")
    return _set_view(session, s)
