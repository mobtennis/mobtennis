from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db.session import get_session
from app.models.match import Match, MatchStatus
from app.models.match_follow import MatchFollow, MatchFollowGranularity

router = APIRouter(prefix="/api/follows/matches", tags=["follows"])


class MatchFollowIn(BaseModel):
    match_id: int
    granularity: MatchFollowGranularity = MatchFollowGranularity.KEY_MOMENTS


class MatchFollowOut(BaseModel):
    match_id: int
    granularity: MatchFollowGranularity


def _token(x: str | None) -> str:
    if not x:
        raise HTTPException(401, "Missing X-User-Token header")
    return x


@router.get("", response_model=list[MatchFollowOut])
def list_match_follows(
    x_user_token: str | None = Header(default=None),
    session: Session = Depends(get_session),
):
    token = _token(x_user_token)
    rows = session.exec(
        select(MatchFollow).where(MatchFollow.user_token == token)
    ).all()
    return [MatchFollowOut(match_id=r.match_id, granularity=r.granularity) for r in rows]


@router.post("", response_model=MatchFollowOut)
def add_match_follow(
    payload: MatchFollowIn,
    x_user_token: str | None = Header(default=None),
    session: Session = Depends(get_session),
):
    token = _token(x_user_token)

    match = session.get(Match, payload.match_id)
    if not match:
        raise HTTPException(404, "Match not found")
    if match.status in (MatchStatus.FINISHED, MatchStatus.RETIRED,
                        MatchStatus.WALKOVER, MatchStatus.CANCELLED):
        raise HTTPException(400, "Cannot follow a match that has already ended")

    existing = session.exec(
        select(MatchFollow).where(
            MatchFollow.user_token == token,
            MatchFollow.match_id == payload.match_id,
        )
    ).first()
    if existing:
        existing.granularity = payload.granularity
        session.add(existing)
        session.commit()
        return MatchFollowOut(match_id=existing.match_id, granularity=existing.granularity)

    f = MatchFollow(
        user_token=token,
        match_id=payload.match_id,
        granularity=payload.granularity,
    )
    session.add(f)
    session.commit()
    return MatchFollowOut(match_id=f.match_id, granularity=f.granularity)


class MatchFollowDelete(BaseModel):
    match_id: int


@router.delete("")
def remove_match_follow(
    payload: MatchFollowDelete,
    x_user_token: str | None = Header(default=None),
    session: Session = Depends(get_session),
):
    token = _token(x_user_token)
    existing = session.exec(
        select(MatchFollow).where(
            MatchFollow.user_token == token,
            MatchFollow.match_id == payload.match_id,
        )
    ).first()
    if existing:
        session.delete(existing)
        session.commit()
    return {"ok": True}
