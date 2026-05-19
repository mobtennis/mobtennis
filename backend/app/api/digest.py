from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.db.session import get_session
from app.models.digest import EditorialDigest
from app.schemas.digest import DigestDetail, DigestSummary

router = APIRouter(prefix="/api/digests", tags=["digests"])


@router.get("", response_model=list[DigestSummary])
def list_digests(
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
):
    """Archive list, newest first. Body is omitted to keep payloads small."""
    rows = session.exec(
        select(EditorialDigest)
        .order_by(EditorialDigest.week_start.desc())
        .limit(limit)
    ).all()
    return [
        DigestSummary(
            week_start=r.week_start,
            headline=r.headline,
            generated_at=r.generated_at,
        )
        for r in rows
    ]


@router.get("/latest", response_model=DigestDetail)
def latest_digest(session: Session = Depends(get_session)):
    row = session.exec(
        select(EditorialDigest).order_by(EditorialDigest.week_start.desc()).limit(1)
    ).first()
    if not row:
        raise HTTPException(404, "No digest available yet")
    return _to_detail(row)


@router.get("/{week_start}", response_model=DigestDetail)
def get_digest(week_start: date, session: Session = Depends(get_session)):
    """week_start is the Monday of the ISO week, e.g. 2026-05-11."""
    row = session.exec(
        select(EditorialDigest).where(EditorialDigest.week_start == week_start)
    ).first()
    if not row:
        raise HTTPException(404, "Digest not found for that week")
    return _to_detail(row)


def _to_detail(row: EditorialDigest) -> DigestDetail:
    return DigestDetail(
        week_start=row.week_start,
        headline=row.headline,
        generated_at=row.generated_at,
        body_md=row.body_md,
        model_name=row.model_name,
    )
