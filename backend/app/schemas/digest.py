from datetime import date, datetime

from pydantic import BaseModel


class DigestSummary(BaseModel):
    """List-card shape. No body — keeps the archive list small."""
    week_start: date
    headline: str
    generated_at: datetime


class DigestDetail(DigestSummary):
    body_md: str
    model_name: str
