from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db.session import get_session
from app.models.follow import Follow, FollowKind

router = APIRouter(
    prefix="/api/follows",
    tags=["follows"],
    # App-only endpoint. Web does not personalize — see docs/identity.md.
    # The X-User-Token header is the device-bound account id; auth only
    # enters the flow when transferring an account between devices.
)


class FollowIn(BaseModel):
    kind: FollowKind
    target_slug: str
    # Required for tournaments (Rome ATP vs Rome WTA share a slug),
    # ignored for players (player slugs are globally unique).
    target_tour: str | None = None


class FollowOut(BaseModel):
    kind: FollowKind
    target_slug: str
    target_tour: str | None = None


def _token(x: str | None) -> str:
    if not x:
        raise HTTPException(401, "Missing X-User-Token header")
    return x


def _normalize_tour(payload: FollowIn) -> str | None:
    """Tournaments must carry tour; players don't."""
    if payload.kind == FollowKind.TOURNAMENT:
        return payload.target_tour
    return None


@router.get("", response_model=list[FollowOut])
def list_follows(
    x_user_token: str | None = Header(default=None),
    session: Session = Depends(get_session),
):
    token = _token(x_user_token)
    rows = session.exec(select(Follow).where(Follow.user_token == token)).all()
    return [
        FollowOut(kind=f.kind, target_slug=f.target_slug, target_tour=f.target_tour)
        for f in rows
    ]


@router.post("", response_model=FollowOut)
def add_follow(
    payload: FollowIn,
    x_user_token: str | None = Header(default=None),
    session: Session = Depends(get_session),
):
    token = _token(x_user_token)
    tour = _normalize_tour(payload)

    stmt = select(Follow).where(
        Follow.user_token == token,
        Follow.kind == payload.kind,
        Follow.target_slug == payload.target_slug,
    )
    if tour is not None:
        stmt = stmt.where(Follow.target_tour == tour)
    existing = session.exec(stmt).first()
    if existing:
        return FollowOut(
            kind=existing.kind,
            target_slug=existing.target_slug,
            target_tour=existing.target_tour,
        )

    f = Follow(
        user_token=token,
        kind=payload.kind,
        target_slug=payload.target_slug,
        target_tour=tour,
    )
    session.add(f)
    session.commit()
    return FollowOut(kind=f.kind, target_slug=f.target_slug, target_tour=f.target_tour)


@router.delete("")
def remove_follow(
    payload: FollowIn,
    x_user_token: str | None = Header(default=None),
    session: Session = Depends(get_session),
):
    token = _token(x_user_token)
    tour = _normalize_tour(payload)

    stmt = select(Follow).where(
        Follow.user_token == token,
        Follow.kind == payload.kind,
        Follow.target_slug == payload.target_slug,
    )
    if tour is not None:
        stmt = stmt.where(Follow.target_tour == tour)
    existing = session.exec(stmt).first()
    if existing:
        session.delete(existing)
        session.commit()
    return {"ok": True}
