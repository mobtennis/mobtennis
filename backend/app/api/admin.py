"""Admin-only endpoints.

Gated behind `ADMIN_KEY` env var via `?key=<value>` query param. The
data exposed here isn't load-bearing for the public site — it's an
operator surface for things like Google Ads campaign briefs.

The check is intentionally light:
  - One operator, one shared key.
  - Data isn't sensitive (campaign briefs are derived from the same
    public digest source_json).
  - Adding real auth (sessions, JWT, OAuth) for a one-user route
    would add far more attack surface than it removes.

Refuse access if ADMIN_KEY is unset — fails closed rather than
serving the data publicly.
"""

from __future__ import annotations

import json
import os
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db.session import get_session
from app.models.digest import EditorialDigest
from app.schemas.digest import CampaignBrief, CampaignBriefsResponse
from app.services.editorial_digest import generate_digest

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _require_admin_key(key: Annotated[str | None, Query()] = None) -> None:
    expected = os.environ.get("ADMIN_KEY")
    if not expected:
        # No key configured server-side → admin routes are completely off.
        raise HTTPException(404, "Not found")
    if key != expected:
        raise HTTPException(401, "Bad admin key")


@router.get(
    "/campaigns/latest",
    response_model=CampaignBriefsResponse,
    dependencies=[Depends(_require_admin_key)],
)
def latest_campaigns(session: Session = Depends(get_session)):
    row = session.exec(
        select(EditorialDigest)
        .where(EditorialDigest.campaign_briefs_json.is_not(None))
        .order_by(EditorialDigest.week_start.desc())
        .limit(1)
    ).first()
    if not row:
        raise HTTPException(404, "No digest with campaign briefs available yet")
    return _to_briefs_response(row)


@router.get(
    "/campaigns/{week_start}",
    response_model=CampaignBriefsResponse,
    dependencies=[Depends(_require_admin_key)],
)
def campaigns_for_week(
    week_start: date,
    session: Session = Depends(get_session),
):
    row = session.exec(
        select(EditorialDigest).where(EditorialDigest.week_start == week_start)
    ).first()
    if not row:
        raise HTTPException(404, "Digest not found for that week")
    if not row.campaign_briefs_json:
        raise HTTPException(
            404,
            "Digest has no campaign briefs (predates the feature or LLM "
            "returned none — regenerate with --force to backfill)",
        )
    return _to_briefs_response(row)


def _to_briefs_response(row: EditorialDigest) -> CampaignBriefsResponse:
    raw = json.loads(row.campaign_briefs_json or "[]")
    briefs = [CampaignBrief(**b) for b in raw]
    return CampaignBriefsResponse(
        week_start=row.week_start,
        headline=row.headline,
        generated_at=row.generated_at,
        briefs=briefs,
    )


class GenerateDigestBody(BaseModel):
    """Body for the ad-hoc-digest endpoint. Both fields optional."""
    force: bool = False  # bypass the 24h rate-limit gate
    notes: list[str] = []  # verified human-supplied facts to weave in


class GenerateDigestResponse(BaseModel):
    status: str  # 'created' | 'skipped_rate_limited' | 'skipped_no_facts' | 'failed'
    message: str = ""
    week_start: date | None = None
    headline: str | None = None


@router.post(
    "/digests/generate",
    response_model=GenerateDigestResponse,
    dependencies=[Depends(_require_admin_key)],
)
def generate_ad_hoc_digest(
    body: GenerateDigestBody = Body(default_factory=GenerateDigestBody),
    session: Session = Depends(get_session),
):
    """Generate a digest right now covering everything since the last one.

    Rate-limited at 24h: if the most recent digest was published within
    the last day, returns `skipped_rate_limited` with a `message`
    explaining when the next run is allowed. `force=true` bypasses
    the gate for genuine re-runs (data fix, prompt iteration).

    `notes` is a list of verified facts to feed Claude in the
    EDITORIAL NOTES section of the prompt — useful when a milestone or
    off-court story isn't captured by the match/news ingest.
    """
    result = generate_digest(
        session,
        force=body.force,
        editorial_notes=body.notes or None,
    )
    return GenerateDigestResponse(
        status=result.status,
        message=result.message,
        week_start=result.row.week_start if result.row else None,
        headline=result.row.headline if result.row else None,
    )
