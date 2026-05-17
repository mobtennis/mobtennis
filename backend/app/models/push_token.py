from datetime import datetime

from sqlmodel import Field, SQLModel


class PushToken(SQLModel, table=True):
    """One row per device. user_token is unique — re-registering an Expo token
    on the same device updates the existing row in-place."""

    __tablename__ = "push_tokens"

    id: int | None = Field(default=None, primary_key=True)
    user_token: str = Field(index=True, unique=True)
    expo_token: str = Field(index=True)
    platform: str | None = None  # "ios" | "android"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
