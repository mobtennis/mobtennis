"""Public Call the Shot endpoint — predict-where-the-ball-goes."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.db.session import get_session
from app.models.call_the_shot import CallTheShotItem
from app.schemas.call_the_shot import CallTheShotItemView

router = APIRouter(prefix="/api/call-the-shot", tags=["call-the-shot"])


def _to_view(row: CallTheShotItem) -> CallTheShotItemView:
    try:
        options = json.loads(row.options_json or "[]")
    except json.JSONDecodeError:
        options = []
    return CallTheShotItemView(
        id=row.id,
        video_id=row.video_id,
        start_at_s=row.start_at_s,
        pause_at_s=row.pause_at_s,
        caption=row.caption,
        options=options,
        correct_index=row.correct_index,
        source_url=row.source_url,
    )


@router.get("/items", response_model=list[CallTheShotItemView])
def list_items(session: Session = Depends(get_session)):
    """All visible items, ordered by (video_id, start_at_s) so the
    frontend gets them play-ready. Same sort the frontend used to do
    client-side."""
    rows = session.exec(
        select(CallTheShotItem)
        .where(CallTheShotItem.is_hidden == False)  # noqa: E712
        .order_by(CallTheShotItem.video_id, CallTheShotItem.start_at_s)
    ).all()
    return [_to_view(r) for r in rows]
