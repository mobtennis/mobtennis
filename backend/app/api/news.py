from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from app.db.session import get_session
from app.models.news import NewsItem
from app.schemas.news import NewsItemSummary
from app.services.news import clean_summary

router = APIRouter(prefix="/api/news", tags=["news"])


def _to_summary(item: NewsItem) -> NewsItemSummary:
    summary_text, fallback_img = clean_summary(item.summary)
    return NewsItemSummary(
        id=item.id,
        source=item.source,
        source_url=item.source_url,
        title=item.title,
        summary=summary_text,
        image_url=item.image_url or fallback_img,
        author=item.author,
        published_at=item.published_at,
        player_slugs=[s for s in (item.player_slugs or "").split(",") if s],
        tournament_slugs=[s for s in (item.tournament_slugs or "").split(",") if s],
    )


@router.get("", response_model=list[NewsItemSummary])
def list_news(
    player_slug: str | None = None,
    tournament_slug: str | None = None,
    source: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    # Cursor for "load more" pagination — strictly older than this
    # timestamp. The client passes the published_at of the oldest news
    # item it already has, then appends the returned batch.
    before: datetime | None = None,
    session: Session = Depends(get_session),
):
    stmt = select(NewsItem)
    if source:
        stmt = stmt.where(NewsItem.source == source)
    if player_slug:
        stmt = stmt.where(NewsItem.player_slugs.contains(player_slug))
    if tournament_slug:
        stmt = stmt.where(NewsItem.tournament_slugs.contains(tournament_slug))
    if before is not None:
        stmt = stmt.where(NewsItem.published_at < before)
    stmt = stmt.order_by(NewsItem.published_at.desc()).limit(limit)
    return [_to_summary(n) for n in session.exec(stmt).all()]
