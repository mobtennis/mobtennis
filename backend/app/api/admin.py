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
from app.models.spot_the_ball import SpotTheBallPuzzle, SpotTheBallSkip
from app.schemas.digest import CampaignBrief, CampaignBriefsResponse
from app.schemas.player import PlayerImageView
from app.schemas.spot_the_ball import (
    CandidateStats,
    CandidateView,
    ScheduleResponse,
    SpotTheBallPuzzleView,
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
# Spot-the-Ball calibration
# ---------------------------------------------------------------------------


class CalibrateBallBody(BaseModel):
    """Ball position in image-space as percentages (0-100). Match the
    storage shape on the row so the field is stable at any display
    size."""
    ball_x_pct: float
    ball_y_pct: float


@router.post(
    "/spot-the-ball/{puzzle_date}/ball",
    response_model=SpotTheBallPuzzleView,
    dependencies=[Depends(_require_admin_key)],
)
def calibrate_ball(
    puzzle_date: date,
    body: CalibrateBallBody,
    session: Session = Depends(get_session),
):
    """Set the true ball coordinates for a seeded puzzle. The play
    page exposes a calibration mode (`?calibrate=ADMIN_KEY`) that
    POSTs here when an operator clicks on the actual ball; bypasses
    needing to edit JSON / inspect images in a separate tool."""
    row = session.exec(
        select(SpotTheBallPuzzle).where(SpotTheBallPuzzle.puzzle_date == puzzle_date)
    ).first()
    if not row:
        raise HTTPException(404, "Puzzle not found")
    # Clamp to the legal % range — guards against floating-point drift
    # if the click lands a pixel outside the image rect.
    row.ball_x_pct = max(0.0, min(100.0, body.ball_x_pct))
    row.ball_y_pct = max(0.0, min(100.0, body.ball_y_pct))
    session.add(row)
    session.commit()
    session.refresh(row)
    return SpotTheBallPuzzleView(
        puzzle_date=row.puzzle_date,
        image_url=row.image_url,
        image_w=row.image_w,
        image_h=row.image_h,
        ball_x_pct=row.ball_x_pct,
        ball_y_pct=row.ball_y_pct,
        caption=row.caption,
        credit=row.credit,
        license_url=row.license_url,
        source_url=row.source_url,
    )


# ---------------------------------------------------------------------------
# Spot-the-Ball admin builder — content pipeline
# ---------------------------------------------------------------------------


def _next_scheduled_date(session: Session) -> date:
    """The day after the latest existing puzzle, or today if none exist
    yet. Admin builds a queue of future puzzles by scheduling
    consecutively; cron promotion happens automatically as dates land."""
    from datetime import timedelta
    last = session.exec(
        select(SpotTheBallPuzzle.puzzle_date)
        .order_by(SpotTheBallPuzzle.puzzle_date.desc())
        .limit(1)
    ).first()
    today = date.today()
    if not last:
        return today
    return max(last + timedelta(days=1), today + timedelta(days=1))


def _commons_file_page_url(upload_url: str) -> str | None:
    """Derive the Commons File: page URL from an upload.wikimedia.org
    URL so the puzzle's source_url links back to the original page
    with full provenance + licence details."""
    # https://upload.wikimedia.org/wikipedia/commons/[thumb/]X/YZ/Filename.ext[/...]
    import re
    from urllib.parse import quote
    m = re.match(
        r"https://upload\.wikimedia\.org/wikipedia/commons/(?:thumb/)?[0-9a-f]/[0-9a-f]{2}/([^/?#]+)",
        upload_url,
    )
    if not m:
        return None
    filename = m.group(1)
    return f"https://commons.wikimedia.org/wiki/File:{quote(filename)}"


def _player_query_candidate(
    session: Session, exclude_image_ids: set[int],
) -> tuple[PlayerImage, Player] | None:
    """Find the next PlayerImage to offer the admin. Criteria:

      * Player has a ranking signal (current_rank known OR career_high
        ≤ 300) — filters out the long tail of obscure rows from
        our lazy enrichment.
      * Image is hero-eligible (landscape, ≥1000px wide) — action
        shots, not portraits. Tennis players holding a racket.
      * Image isn't already used in a puzzle AND hasn't been skipped.
      * Image isn't hidden.

    Ordered by image id (stable, predictable progression through
    the queue) rather than randomly so re-opens land on the same
    photo as before any skip/schedule action.
    """
    stmt = (
        select(PlayerImage, Player)
        .join(Player, Player.id == PlayerImage.player_id)
        .where(
            PlayerImage.is_hero_eligible == True,  # noqa: E712
            PlayerImage.is_hidden == False,        # noqa: E712
            (Player.current_rank.is_not(None)) | (Player.career_high_rank <= 300),
        )
        .order_by(PlayerImage.id.asc())
    )
    if exclude_image_ids:
        stmt = stmt.where(PlayerImage.id.notin_(exclude_image_ids))
    return session.exec(stmt).first()


def _excluded_image_ids(session: Session) -> set[int]:
    # SQLModel returns scalars (not 1-tuples) when the select picks a
    # single column, so iterate as plain ints.
    used = {
        r for r in session.exec(
            select(SpotTheBallPuzzle.player_image_id)
            .where(SpotTheBallPuzzle.player_image_id.is_not(None))
        ).all()
        if r is not None
    }
    skipped = set(session.exec(select(SpotTheBallSkip.player_image_id)).all())
    return used | skipped


def _candidate_view(img: PlayerImage, player: Player) -> CandidateView:
    name = player.full_name or ""
    return CandidateView(
        player_image_id=img.id,
        image_url=img.url,
        player_slug=player.slug,
        player_name=name,
        suggested_caption=name,
        credit=img.credit,
        license_url=img.license_url,
        source_url=_commons_file_page_url(img.url),
        width=img.width,
        height=img.height,
    )


def _candidate_stats(session: Session) -> CandidateStats:
    excluded = _excluded_image_ids(session)
    total_eligible = session.exec(
        select(PlayerImage.id)
        .join(Player, Player.id == PlayerImage.player_id)
        .where(
            PlayerImage.is_hero_eligible == True,  # noqa: E712
            PlayerImage.is_hidden == False,        # noqa: E712
            (Player.current_rank.is_not(None)) | (Player.career_high_rank <= 300),
        )
    ).all()
    remaining = len([i for i in total_eligible if i not in excluded])
    queued = len(session.exec(
        select(SpotTheBallPuzzle.id)
        .where(SpotTheBallPuzzle.is_published == False)  # noqa: E712
        .where(SpotTheBallPuzzle.ball_x_pct.is_not(None))
    ).all())
    published = len(session.exec(
        select(SpotTheBallPuzzle.id)
        .where(SpotTheBallPuzzle.is_published == True)  # noqa: E712
    ).all())
    skipped = len(session.exec(select(SpotTheBallSkip.id).distinct()).all())
    return CandidateStats(
        candidates_remaining=remaining,
        queued=queued,
        published=published,
        skipped=skipped,
    )


def _fetch_next_candidate(session: Session) -> CandidateView | None:
    found = _player_query_candidate(session, _excluded_image_ids(session))
    if not found:
        return None
    img, player = found
    return _candidate_view(img, player)


@router.get(
    "/spot-the-ball/builder/next",
    dependencies=[Depends(_require_admin_key)],
)
def builder_next_candidate(session: Session = Depends(get_session)):
    """Returns the next candidate + a stats snapshot. Used on initial
    page load and re-fetched after each skip/schedule action."""
    return {
        "candidate": _fetch_next_candidate(session),
        "stats": _candidate_stats(session),
    }


class SkipBody(BaseModel):
    player_image_id: int


@router.post(
    "/spot-the-ball/builder/skip",
    dependencies=[Depends(_require_admin_key)],
)
def builder_skip(body: SkipBody, session: Session = Depends(get_session)):
    """Drop this image from the candidate pool permanently."""
    existing = session.exec(
        select(SpotTheBallSkip).where(
            SpotTheBallSkip.player_image_id == body.player_image_id,
        )
    ).first()
    if not existing:
        session.add(SpotTheBallSkip(player_image_id=body.player_image_id))
        session.commit()
    return {
        "candidate": _fetch_next_candidate(session),
        "stats": _candidate_stats(session),
    }


class QueueItem(BaseModel):
    """One row in the admin queue listing. Lighter than the public
    puzzle view because the list page renders dozens at once."""
    puzzle_date: date
    caption: str
    image_url: str           # current (post-Replicate when published)
    original_image_url: str | None
    is_published: bool
    ball_x_pct: float | None
    ball_y_pct: float | None


@router.get(
    "/spot-the-ball/all",
    response_model=list[QueueItem],
    dependencies=[Depends(_require_admin_key)],
)
def builder_all(session: Session = Depends(get_session)):
    """Every puzzle the admin has ever touched, newest first. Drives
    the queue/verification page — shows scheduled-but-not-processed
    alongside already-published ones, with the status badge so the
    operator knows where each one stands."""
    rows = session.exec(
        select(SpotTheBallPuzzle)
        .where(SpotTheBallPuzzle.ball_x_pct.is_not(None))
        .order_by(SpotTheBallPuzzle.puzzle_date.desc())
    ).all()
    return [
        QueueItem(
            puzzle_date=r.puzzle_date,
            caption=r.caption,
            image_url=r.image_url,
            original_image_url=r.original_image_url,
            is_published=r.is_published,
            ball_x_pct=r.ball_x_pct,
            ball_y_pct=r.ball_y_pct,
        )
        for r in rows
    ]


@router.get(
    "/spot-the-ball/queue",
    response_model=list[SpotTheBallPuzzleView],
    dependencies=[Depends(_require_admin_key)],
)
def builder_queue(session: Session = Depends(get_session)):
    """Scheduled-but-not-yet-processed puzzles. The local Replicate
    processor reads this to know which rows need inpainting."""
    rows = session.exec(
        select(SpotTheBallPuzzle)
        .where(SpotTheBallPuzzle.is_published == False)  # noqa: E712
        .where(SpotTheBallPuzzle.ball_x_pct.is_not(None))
        .order_by(SpotTheBallPuzzle.puzzle_date.asc())
    ).all()
    return [
        SpotTheBallPuzzleView(
            puzzle_date=r.puzzle_date,
            image_url=r.image_url,
            original_image_url=r.original_image_url,
            image_w=r.image_w,
            image_h=r.image_h,
            ball_x_pct=r.ball_x_pct or 50.0,
            ball_y_pct=r.ball_y_pct or 50.0,
            caption=r.caption,
            credit=r.credit,
            license_url=r.license_url,
            source_url=r.source_url,
        )
        for r in rows
    ]


class ScheduleBody(BaseModel):
    player_image_id: int
    ball_x_pct: float
    ball_y_pct: float
    caption: str | None = None  # admin override; default = suggested


@router.post(
    "/spot-the-ball/builder/schedule",
    response_model=ScheduleResponse,
    dependencies=[Depends(_require_admin_key)],
)
def builder_schedule(
    body: ScheduleBody,
    session: Session = Depends(get_session),
):
    """Schedule this image as a future puzzle. The row enters the
    queue with is_published=False — invisible to the public until the
    local Replicate processor runs and flips it.
    """
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

    scheduled_date = _next_scheduled_date(session)
    caption = body.caption or player.full_name or "Spot the ball"

    row = SpotTheBallPuzzle(
        puzzle_date=scheduled_date,
        # Until the processor runs, image_url is the Wikimedia source
        # (public won't see this because is_published gates access).
        image_url=img.url,
        original_image_url=img.url,
        image_w=img.width,
        image_h=img.height,
        ball_x_pct=max(0.0, min(100.0, body.ball_x_pct)),
        ball_y_pct=max(0.0, min(100.0, body.ball_y_pct)),
        caption=caption,
        credit=img.credit,
        license_url=img.license_url,
        source_url=_commons_file_page_url(img.url),
        player_image_id=img.id,
        is_published=False,
    )
    session.add(row)
    session.commit()
    return ScheduleResponse(
        scheduled_date=scheduled_date,
        next_candidate=_fetch_next_candidate(session),
        stats=_candidate_stats(session),
    )
