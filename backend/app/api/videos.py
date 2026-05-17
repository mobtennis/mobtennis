from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from app.db.session import get_session
from app.models.video import VideoItem
from app.schemas.video import VideoItemSummary

router = APIRouter(prefix="/api/videos", tags=["videos"])


def _to_summary(v: VideoItem) -> VideoItemSummary:
    return VideoItemSummary(
        id=v.id or 0,
        source=v.source,
        video_id=v.video_id,
        title=v.title,
        summary=v.summary,
        thumbnail_url=v.thumbnail_url,
        channel_name=v.channel_name,
        published_at=v.published_at,
        player_slugs=[s for s in (v.player_slugs or "").split(",") if s],
        tournament_slugs=[s for s in (v.tournament_slugs or "").split(",") if s],
        match_id=v.match_id,
        is_portrait=v.is_portrait,
    )


@router.get("", response_model=list[VideoItemSummary])
def list_videos(
    limit: int = Query(20, ge=1, le=100),
    player_slug: str | None = None,
    tournament_slug: str | None = None,
    match_id: int | None = None,
    # Cursor for "load more": strictly older than this timestamp.
    before: datetime | None = None,
    session: Session = Depends(get_session),
):
    """Latest highlight videos, newest first.

    Filters mirror /api/news: pass `player_slug` and/or
    `tournament_slug` to narrow to a specific person or event. `match_id`
    targets the (future) match-level fuzzy-match association — only
    returns videos that have been tied to that specific Match row.
    Pass `before=<ISO timestamp>` to paginate older items.
    """
    stmt = select(VideoItem).order_by(VideoItem.published_at.desc()).limit(limit)
    if player_slug:
        # Title-tagged slugs are comma-joined; use SQL LIKE for substring
        # match. Same approach as news_fanout in services/news_fanout.py.
        stmt = stmt.where(VideoItem.player_slugs.like(f"%{player_slug}%"))
    if tournament_slug:
        stmt = stmt.where(VideoItem.tournament_slugs.like(f"%{tournament_slug}%"))
    if match_id is not None:
        stmt = stmt.where(VideoItem.match_id == match_id)
    if before is not None:
        stmt = stmt.where(VideoItem.published_at < before)
    rows = session.exec(stmt).all()
    return [_to_summary(v) for v in rows]
