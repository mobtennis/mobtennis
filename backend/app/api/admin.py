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
from app.models.player import Player
from app.models.player_image import PlayerImage
from app.models.spot_the_ball import SpotTheBallImage, SpotTheBallSet, SpotTheBallSkip
from app.schemas.digest import CampaignBrief, CampaignBriefsResponse
from app.schemas.player import PlayerImageView
from app.schemas.spot_the_ball import (
    CandidateStats,
    CandidateView,
    QueueImageItem,
    QueueResponse,
    ScheduleResponse,
    SpotTheBallImageView,
    SpotTheBallSetView,
)
from app.services.editorial_digest import generate_digest
from app.services.players_image_enrich import _sync_primary_pointer

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


# ---------------------------------------------------------------------------
# Player image management
# ---------------------------------------------------------------------------


def _load_player_image(
    session: Session, slug: str, image_id: int,
) -> tuple[Player, PlayerImage]:
    player = session.exec(select(Player).where(Player.slug == slug)).first()
    if not player:
        raise HTTPException(404, "Player not found")
    img = session.exec(
        select(PlayerImage).where(
            PlayerImage.id == image_id,
            PlayerImage.player_id == player.id,
        )
    ).first()
    if not img:
        raise HTTPException(404, "Image not found for that player")
    return player, img


@router.post(
    "/players/{slug}/images/{image_id}/primary",
    response_model=PlayerImageView,
    dependencies=[Depends(_require_admin_key)],
)
def set_player_image_primary(
    slug: str, image_id: int, session: Session = Depends(get_session),
):
    """Mark this image as the primary for the player. Demotes whichever
    image was primary before; re-syncs Player.image_url to the new one."""
    player, target = _load_player_image(session, slug, image_id)
    if target.is_hidden:
        raise HTTPException(400, "Cannot set a hidden image as primary; unhide it first")

    others = session.exec(
        select(PlayerImage).where(
            PlayerImage.player_id == player.id,
            PlayerImage.is_primary == True,  # noqa: E712
            PlayerImage.id != target.id,
        )
    ).all()
    for o in others:
        o.is_primary = False
        session.add(o)
    target.is_primary = True
    session.add(target)
    _sync_primary_pointer(session, player)
    session.commit()
    session.refresh(target)
    return PlayerImageView(
        id=target.id, url=target.url, source=target.source,
        source_url=target.source_url, credit=target.credit,
        license_url=target.license_url, width=target.width, height=target.height,
        is_primary=target.is_primary, is_hidden=target.is_hidden,
        is_hero=target.is_hero, is_hero_eligible=target.is_hero_eligible,
    )


@router.post(
    "/players/{slug}/images/{image_id}/hero",
    response_model=PlayerImageView,
    dependencies=[Depends(_require_admin_key)],
)
def set_player_image_hero(
    slug: str, image_id: int, session: Session = Depends(get_session),
):
    """Mark this image as the hero (landscape header band) for the
    player. Demotes the prior hero. Bypasses the is_hero_eligible
    heuristic so admins can override the auto-pick for a portrait
    image they actively want (e.g. a stylised studio shot that
    crops well even without classifier approval)."""
    player, target = _load_player_image(session, slug, image_id)
    if target.is_hidden:
        raise HTTPException(400, "Cannot set a hidden image as hero; unhide it first")

    others = session.exec(
        select(PlayerImage).where(
            PlayerImage.player_id == player.id,
            PlayerImage.is_hero == True,  # noqa: E712
            PlayerImage.id != target.id,
        )
    ).all()
    for o in others:
        o.is_hero = False
        session.add(o)
    target.is_hero = True
    session.add(target)
    _sync_primary_pointer(session, player)
    session.commit()
    session.refresh(target)
    return PlayerImageView(
        id=target.id, url=target.url, source=target.source,
        source_url=target.source_url, credit=target.credit,
        license_url=target.license_url, width=target.width, height=target.height,
        is_primary=target.is_primary, is_hidden=target.is_hidden,
        is_hero=target.is_hero, is_hero_eligible=target.is_hero_eligible,
    )


@router.post(
    "/players/{slug}/images/{image_id}/hidden",
    response_model=PlayerImageView,
    dependencies=[Depends(_require_admin_key)],
)
def set_player_image_hidden(
    slug: str, image_id: int,
    hidden: bool = Query(True),
    session: Session = Depends(get_session),
):
    """Hide or unhide an image. Hiding the current primary triggers a
    re-sync that picks the next-best non-hidden image as primary so
    the public site never serves an image we hid."""
    player, target = _load_player_image(session, slug, image_id)
    target.is_hidden = hidden
    if hidden and target.is_primary:
        target.is_primary = False
    session.add(target)
    _sync_primary_pointer(session, player)
    session.commit()
    session.refresh(target)
    return PlayerImageView(
        id=target.id, url=target.url, source=target.source,
        source_url=target.source_url, credit=target.credit,
        license_url=target.license_url, width=target.width, height=target.height,
        is_primary=target.is_primary, is_hidden=target.is_hidden,
        is_hero=target.is_hero, is_hero_eligible=target.is_hero_eligible,
    )



# ---------------------------------------------------------------------------
# Spot-the-Ball admin — builder, queue, bundling, calibration, inpaint review
# ---------------------------------------------------------------------------


# Suggested caption is just the player name for now. Operator can pass
# a `caption` override on the schedule body if they want themed copy.


def _next_candidate_for_builder(session: Session) -> CandidateView | None:
    """Find the next PlayerImage to offer the admin builder. Filters
    by ranking + hero-eligibility, excludes already-used and skipped
    images. Orders newest-first by year-in-filename (so the operator
    sees current photos before old ones)."""
    import re

    _YEAR_RE = re.compile(r"(?<!\d)(19[89]\d|20[0-2]\d)(?!\d)")

    def _photo_year(url: str) -> int:
        years = _YEAR_RE.findall(url or "")
        return max((int(y) for y in years), default=0)

    used_ids: set[int] = set()
    for r in session.exec(
        select(SpotTheBallImage.source_player_image_id).where(
            SpotTheBallImage.source_player_image_id.is_not(None),
        )
    ).all():
        if r is not None:
            used_ids.add(r)
    skipped_ids = set(session.exec(select(SpotTheBallSkip.player_image_id)).all())
    exclude = used_ids | skipped_ids

    stmt = (
        select(PlayerImage, Player)
        .join(Player, Player.id == PlayerImage.player_id)
        .where(
            PlayerImage.is_hero_eligible == True,  # noqa: E712
            PlayerImage.is_hidden == False,        # noqa: E712
            (Player.current_rank.is_not(None)) | (Player.career_high_rank <= 300),
        )
    )
    if exclude:
        stmt = stmt.where(PlayerImage.id.notin_(exclude))
    rows = session.exec(stmt).all()
    if not rows:
        return None
    rows.sort(key=lambda t: (-_photo_year(t[0].url), -t[0].id))
    img, player = rows[0]
    return CandidateView(
        player_image_id=img.id,
        image_url=img.url,
        player_slug=player.slug,
        player_name=player.full_name or "",
        suggested_caption=player.full_name or "",
        credit=img.credit,
        license_url=img.license_url,
        source_url=_commons_file_page_url(img.url),
        width=img.width,
        height=img.height,
    )


def _commons_file_page_url(upload_url: str) -> str | None:
    """Derive the Commons File: page URL from the upload URL."""
    import re
    from urllib.parse import quote
    m = re.match(
        r"https://upload\.wikimedia\.org/wikipedia/commons/(?:thumb/)?[0-9a-f]/[0-9a-f]{2}/([^/?#]+)",
        upload_url,
    )
    if not m:
        return None
    return f"https://commons.wikimedia.org/wiki/File:{quote(m.group(1))}"


def _candidate_stats(session: Session) -> CandidateStats:
    used_ids: set[int] = set()
    for r in session.exec(
        select(SpotTheBallImage.source_player_image_id).where(
            SpotTheBallImage.source_player_image_id.is_not(None),
        )
    ).all():
        if r is not None:
            used_ids.add(r)
    skipped_ids = set(session.exec(select(SpotTheBallSkip.player_image_id)).all())
    excluded = used_ids | skipped_ids
    eligible_ids = set(session.exec(
        select(PlayerImage.id)
        .join(Player, Player.id == PlayerImage.player_id)
        .where(
            PlayerImage.is_hero_eligible == True,  # noqa: E712
            PlayerImage.is_hidden == False,        # noqa: E712
            (Player.current_rank.is_not(None)) | (Player.career_high_rank <= 300),
        )
    ).all())
    remaining = len(eligible_ids - excluded)
    pool = len(session.exec(
        select(SpotTheBallImage.id)
        .where(SpotTheBallImage.set_id.is_(None))
    ).all())
    sets_published = len(session.exec(
        select(SpotTheBallSet.id)
        .where(SpotTheBallSet.is_published == True)  # noqa: E712
    ).all())
    skipped = len(skipped_ids)
    return CandidateStats(
        candidates_remaining=remaining,
        pool=pool,
        sets_published=sets_published,
        skipped=skipped,
    )


@router.get(
    "/spot-the-ball/builder/next",
    dependencies=[Depends(_require_admin_key)],
)
def builder_next_candidate(session: Session = Depends(get_session)):
    return {
        "candidate": _next_candidate_for_builder(session),
        "stats": _candidate_stats(session),
    }


class SkipBody(BaseModel):
    player_image_id: int


@router.post(
    "/spot-the-ball/builder/skip",
    dependencies=[Depends(_require_admin_key)],
)
def builder_skip(body: SkipBody, session: Session = Depends(get_session)):
    existing = session.exec(
        select(SpotTheBallSkip).where(
            SpotTheBallSkip.player_image_id == body.player_image_id,
        )
    ).first()
    if not existing:
        session.add(SpotTheBallSkip(player_image_id=body.player_image_id))
        session.commit()
    return {
        "candidate": _next_candidate_for_builder(session),
        "stats": _candidate_stats(session),
    }


class ScheduleBody(BaseModel):
    player_image_id: int
    ball_x_pct: float
    ball_y_pct: float
    caption: str | None = None


@router.post(
    "/spot-the-ball/builder/schedule",
    response_model=ScheduleResponse,
    dependencies=[Depends(_require_admin_key)],
)
def builder_schedule(
    body: ScheduleBody,
    session: Session = Depends(get_session),
):
    """Calibrate an image — it joins the pool (no set yet). The
    bundler picks it up later when 5 distinct players are available."""
    img = session.exec(
        select(PlayerImage).where(PlayerImage.id == body.player_image_id)
    ).first()
    if not img:
        raise HTTPException(404, "Player image not found")
    player = session.exec(
        select(Player).where(Player.id == img.player_id)
    ).first()
    if not player:
        raise HTTPException(404, "Player not found")

    # Idempotency: refuse to create a second SpotTheBallImage for the
    # same source PlayerImage. Double-clicks / stale candidate state
    # previously produced 2-3 STB rows pointing at the same photo,
    # then the bundler dropped copies of the same image into separate
    # sets — players saw the same Sabalenka three days running.
    existing = session.exec(
        select(SpotTheBallImage).where(
            SpotTheBallImage.source_player_image_id == body.player_image_id,
        )
    ).first()
    if existing:
        return ScheduleResponse(
            image_id=existing.id,
            next_candidate=_next_candidate_for_builder(session),
            stats=_candidate_stats(session),
        )

    caption = body.caption or player.full_name or "Spot the ball"
    new = SpotTheBallImage(
        set_id=None,                              # pool — bundler will assign
        position=None,
        image_url=img.url,                        # Wikimedia URL until inpainted
        original_image_url=img.url,
        image_w=img.width,
        image_h=img.height,
        ball_x_pct=max(0.0, min(100.0, body.ball_x_pct)),
        ball_y_pct=max(0.0, min(100.0, body.ball_y_pct)),
        caption=caption,
        credit=img.credit,
        license_url=img.license_url,
        source_url=_commons_file_page_url(img.url),
        source_player_image_id=img.id,
        is_inpainted=False,
    )
    session.add(new)
    session.commit()
    session.refresh(new)
    return ScheduleResponse(
        image_id=new.id,
        next_candidate=_next_candidate_for_builder(session),
        stats=_candidate_stats(session),
    )


@router.post(
    "/spot-the-ball/bundle",
    dependencies=[Depends(_require_admin_key)],
)
def trigger_bundle(session: Session = Depends(get_session)):
    """Run the bundler: forms as many sets-of-5 from the pool as
    variety allows. Idempotent — call any time."""
    from app.services.spot_the_ball_bundler import bundle_pool
    sets = bundle_pool(session)
    return {"sets_created": len(sets), "set_ids": [s.id for s in sets]}


@router.get(
    "/spot-the-ball/queue",
    response_model=QueueResponse,
    dependencies=[Depends(_require_admin_key)],
)
def admin_queue(session: Session = Depends(get_session)):
    """Pool (images awaiting bundling) + published sets newest first.
    Triggers an opportunistic bundle pass on each request so the queue
    is always fresh after a calibration session."""
    from app.services.spot_the_ball_bundler import bundle_pool

    # Opportunistic bundle — cheap when pool is small.
    bundle_pool(session)

    pool_images = session.exec(
        select(SpotTheBallImage)
        .where(SpotTheBallImage.set_id.is_(None))
        .order_by(SpotTheBallImage.id.asc())
    ).all()
    sets = session.exec(
        select(SpotTheBallSet)
        .order_by(SpotTheBallSet.publish_date.desc())
    ).all()
    needing_inpaint = session.exec(
        select(SpotTheBallImage)
        .where(SpotTheBallImage.is_inpainted == False)  # noqa: E712
        .order_by(SpotTheBallImage.id.asc())
    ).all()

    def _to_qi(i: SpotTheBallImage) -> QueueImageItem:
        return QueueImageItem(
            id=i.id,
            set_id=i.set_id,
            position=i.position,
            image_url=i.image_url,
            original_image_url=i.original_image_url,
            caption=i.caption,
            is_inpainted=i.is_inpainted,
            inpaint_attempts=i.inpaint_attempts,
            inpaint_rejected_at=i.inpaint_rejected_at.isoformat() if i.inpaint_rejected_at else None,
            ball_x_pct=i.ball_x_pct,
            ball_y_pct=i.ball_y_pct,
        )

    return QueueResponse(
        images_needing_inpaint=[_to_qi(i) for i in needing_inpaint],
        pool=[_to_qi(i) for i in pool_images],
        sets=[
            SpotTheBallSetView(
                id=s.id,
                title=s.title,
                publish_date=s.publish_date,
                images=[
                    SpotTheBallImageView(
                        id=i.id,
                        position=i.position,
                        image_url=i.image_url,
                        original_image_url=i.original_image_url,
                        image_w=i.image_w,
                        image_h=i.image_h,
                        ball_x_pct=i.ball_x_pct,
                        ball_y_pct=i.ball_y_pct,
                        caption=i.caption,
                        credit=i.credit,
                        license_url=i.license_url,
                        source_url=i.source_url,
                    )
                    for i in session.exec(
                        select(SpotTheBallImage)
                        .where(SpotTheBallImage.set_id == s.id)
                        .order_by(SpotTheBallImage.position.asc())
                    ).all()
                ],
            )
            for s in sets
        ],
    )


@router.get(
    "/spot-the-ball/images/{image_id}",
    response_model=SpotTheBallImageView,
    dependencies=[Depends(_require_admin_key)],
)
def admin_get_image(
    image_id: int,
    session: Session = Depends(get_session),
):
    """Fetch a single SpotTheBallImage (any state) for the
    calibrate/inspect view."""
    img = session.exec(
        select(SpotTheBallImage).where(SpotTheBallImage.id == image_id)
    ).first()
    if not img:
        raise HTTPException(404, "Image not found")
    return SpotTheBallImageView(
        id=img.id,
        position=img.position,
        image_url=img.image_url,
        original_image_url=img.original_image_url,
        image_w=img.image_w,
        image_h=img.image_h,
        ball_x_pct=img.ball_x_pct,
        ball_y_pct=img.ball_y_pct,
        caption=img.caption,
        credit=img.credit,
        license_url=img.license_url,
        source_url=img.source_url,
    )


class CalibrateBody(BaseModel):
    ball_x_pct: float
    ball_y_pct: float


@router.post(
    "/spot-the-ball/images/{image_id}/calibrate",
    response_model=SpotTheBallImageView,
    dependencies=[Depends(_require_admin_key)],
)
def admin_calibrate(
    image_id: int,
    body: CalibrateBody,
    session: Session = Depends(get_session),
):
    """Adjust the ball position on a previously-calibrated image. If
    the image was already inpainted, mark it for re-inpaint by
    clearing is_inpainted (admin needs to run the processor again)."""
    img = session.exec(
        select(SpotTheBallImage).where(SpotTheBallImage.id == image_id)
    ).first()
    if not img:
        raise HTTPException(404, "Image not found")
    img.ball_x_pct = max(0.0, min(100.0, body.ball_x_pct))
    img.ball_y_pct = max(0.0, min(100.0, body.ball_y_pct))
    # Ball moved → existing inpaint is wrong; revert to source so the
    # processor re-runs.
    if img.is_inpainted:
        img.is_inpainted = False
        if img.original_image_url:
            img.image_url = img.original_image_url
    session.add(img)
    session.commit()
    session.refresh(img)
    return SpotTheBallImageView(
        id=img.id, position=img.position,
        image_url=img.image_url, original_image_url=img.original_image_url,
        image_w=img.image_w, image_h=img.image_h,
        ball_x_pct=img.ball_x_pct, ball_y_pct=img.ball_y_pct,
        caption=img.caption, credit=img.credit,
        license_url=img.license_url, source_url=img.source_url,
    )


@router.post(
    "/spot-the-ball/images/{image_id}/remove",
    dependencies=[Depends(_require_admin_key)],
)
def admin_remove_image(
    image_id: int,
    session: Session = Depends(get_session),
):
    """Permanently drop an image. Source PlayerImage joins the skip
    list so the builder doesn't re-offer it."""
    img = session.exec(
        select(SpotTheBallImage).where(SpotTheBallImage.id == image_id)
    ).first()
    if not img:
        raise HTTPException(404, "Image not found")
    if img.source_player_image_id is not None:
        existing = session.exec(
            select(SpotTheBallSkip).where(
                SpotTheBallSkip.player_image_id == img.source_player_image_id,
            )
        ).first()
        if not existing:
            session.add(SpotTheBallSkip(player_image_id=img.source_player_image_id))
    session.delete(img)
    session.commit()
    return {"removed": image_id}


@router.post(
    "/spot-the-ball/images/{image_id}/reject-inpaint",
    dependencies=[Depends(_require_admin_key)],
)
def admin_reject_inpaint(
    image_id: int,
    session: Session = Depends(get_session),
):
    """Flag an inpaint as bad — clear is_inpainted, restore the
    source URL, increment the attempt count. Next processor run will
    re-do this image with a larger mask radius (the processor reads
    inpaint_attempts and bumps mask 20% per attempt)."""
    from datetime import datetime as _dt
    img = session.exec(
        select(SpotTheBallImage).where(SpotTheBallImage.id == image_id)
    ).first()
    if not img:
        raise HTTPException(404, "Image not found")
    img.is_inpainted = False
    img.inpaint_rejected_at = _dt.utcnow()
    if img.original_image_url:
        img.image_url = img.original_image_url
    session.add(img)
    session.commit()
    return {"rejected": image_id, "inpaint_attempts": img.inpaint_attempts}
