from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db.session import get_session
from app.models.push_token import PushToken

router = APIRouter(prefix="/api/push", tags=["push"])


class TokenIn(BaseModel):
    expo_token: str
    platform: str | None = None


def _token(x: str | None) -> str:
    if not x:
        raise HTTPException(401, "Missing X-User-Token header")
    return x


@router.post("/token")
def register_token(
    payload: TokenIn,
    x_user_token: str | None = Header(default=None),
    session: Session = Depends(get_session),
):
    token = _token(x_user_token)
    if not payload.expo_token.startswith(("ExponentPushToken[", "ExpoPushToken[")):
        raise HTTPException(400, "Not a valid Expo push token")

    existing = session.exec(
        select(PushToken).where(PushToken.user_token == token)
    ).first()
    if existing:
        existing.expo_token = payload.expo_token
        existing.platform = payload.platform
        existing.updated_at = datetime.utcnow()
        session.add(existing)
    else:
        session.add(PushToken(
            user_token=token,
            expo_token=payload.expo_token,
            platform=payload.platform,
        ))
    session.commit()
    return {"ok": True}


@router.delete("/token")
def unregister_token(
    x_user_token: str | None = Header(default=None),
    session: Session = Depends(get_session),
):
    token = _token(x_user_token)
    existing = session.exec(
        select(PushToken).where(PushToken.user_token == token)
    ).first()
    if existing:
        session.delete(existing)
        session.commit()
    return {"ok": True}
