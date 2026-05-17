import asyncio
import json
import logging
from datetime import date, datetime, time, timedelta
from enum import Enum

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlmodel import Session, func, select
from tenacity import RetryError

from app.config import settings
from app.db.session import engine
from app.models.match import Match, MatchStatus
from app.models.player import Tour
from app.services.categorize import recategorize_all
from app.api._helpers import match_to_summary
from app.services.follow_event_fanout import fan_out as fan_out_follow_events
from app.services.live import get_live_provider
from app.services.live_hub import hub as live_hub
from app.services.match_event_fanout import fan_out as fan_out_match_events
from app.services.news import sync_news
from app.services.news_fanout import fan_out as fan_out_news
from app.services.youtube import sync_videos
from app.services.rankings_sync import upsert_rankings
from app.services.sync import upsert_live_matches
from app.services.draws_wikipedia import scrape_pending_draws
from app.services.players_bio_enrich import enrich_pending as enrich_players_bios
from app.services.players_socials_enrich import enrich_top_n as enrich_players_socials
from app.services.tournaments_catalog import cleanup_prefixed_brands, upsert_catalog
from app.services.tournaments_enrich import enrich_dates_pending, enrich_pending

# Route scheduler logs through uvicorn's stdout — otherwise job failures
# get swallowed since uvicorn doesn't attach handlers to our loggers.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

_scheduler: AsyncIOScheduler | None = None
_live_task: asyncio.Task | None = None


# ---- Adaptive cadence -------------------------------------------------------


class PollState(str, Enum):
    LIVE = "live"
    IMMINENT = "imminent"
    SCHEDULED = "scheduled"
    IDLE = "idle"


def _decide_cadence(session: Session) -> tuple[PollState, int]:
    """Pick the next poll interval based on what's in the DB right now.

    Order matters: live > imminent > scheduled > idle. Returns (state, seconds).
    """
    now = datetime.utcnow()

    live_count = session.exec(
        select(func.count(Match.id)).where(Match.status == MatchStatus.LIVE)
    ).one()
    if live_count and live_count > 0:
        return PollState.LIVE, settings.live_poll_live

    horizon = now + timedelta(seconds=settings.live_poll_imminent_horizon)
    soonest = session.exec(
        select(func.min(Match.scheduled_at)).where(
            Match.status == MatchStatus.SCHEDULED,
            Match.scheduled_at > now,
        )
    ).one()
    if soonest and soonest <= horizon:
        return PollState.IMMINENT, settings.live_poll_imminent

    end_of_day = datetime.combine(date.today(), time.max)
    today_count = session.exec(
        select(func.count(Match.id)).where(
            Match.status == MatchStatus.SCHEDULED,
            Match.scheduled_at >= now,
            Match.scheduled_at <= end_of_day,
        )
    ).one()
    if today_count and today_count > 0:
        return PollState.SCHEDULED, settings.live_poll_scheduled

    return PollState.IDLE, settings.live_poll_idle


# ---- Polling jobs -----------------------------------------------------------


async def _poll_live_once() -> int:
    """One live-data fetch + upsert. Returns matches touched.

    Match-event diffing happens inside upsert_live_matches; we fan the
    resulting events out to push subscribers in a separate session.
    """
    provider = get_live_provider()
    if provider.name == "noop":
        return 0
    live = await provider.fetch_live()
    if not live:
        return 0
    with Session(engine) as session:
        touched, events = upsert_live_matches(session, live)
    if events:
        try:
            delivered = await fan_out_match_events(events)
            if delivered:
                log.info("match events: %d events → %d match-follow notifications",
                         len(events), delivered)
        except Exception:
            log.exception("match event fan-out failed")
        try:
            follow_delivered = await fan_out_follow_events(events)
            if follow_delivered:
                log.info("match events: %d events → %d player/tournament-follow notifications",
                         len(events), follow_delivered)
        except Exception:
            log.exception("follow event fan-out failed")
    return touched


async def _adaptive_live_loop() -> None:
    """Long-running loop that polls live data and self-paces.

    State decisions read from the DB *after* each upsert so the cadence
    reflects the freshest snapshot. First poll runs immediately on boot.

    When the upstream is unreachable (DNS failure, network glitch, api-tennis
    outage), we don't want to keep hammering at the live cadence — that
    floods the journal and pegs CPU. After NETWORK_FAIL_THRESHOLD consecutive
    network errors we widen the wait to NETWORK_FAIL_BACKOFF_S seconds, and
    log a one-line warning instead of a full traceback per failure.
    """
    log.info("adaptive live poll loop starting")
    network_fails = 0
    while True:
        try:
            touched = await _poll_live_once()
            network_fails = 0
        except (RetryError, httpx.ConnectError, httpx.TimeoutException) as e:
            network_fails += 1
            log.warning(
                "live poll: upstream unreachable (%d consecutive): %s",
                network_fails, _short_err(e),
            )
            touched = 0
        except Exception:
            log.exception("live poll iteration failed")
            touched = 0

        try:
            with Session(engine) as session:
                state, seconds = _decide_cadence(session)
        except Exception:
            log.exception("cadence decision failed; falling back to scheduled")
            state, seconds = PollState.SCHEDULED, settings.live_poll_scheduled

        # Circuit-break: after a streak of network failures, throttle the
        # poll cadence way down. Lets DNS/network heal and stops journald
        # from drowning. We still try periodically so the service self-heals
        # without a manual restart.
        if network_fails >= NETWORK_FAIL_THRESHOLD:
            seconds = max(seconds, NETWORK_FAIL_BACKOFF_S)
            state = PollState.IDLE

        if touched or state != PollState.IDLE:
            log.info(
                "live poll: touched=%d, next in %ds (state=%s)",
                touched, seconds, state.value,
            )
        await asyncio.sleep(seconds)


# Failure-handling tuning. After this many consecutive network errors,
# widen the gap between polls to BACKOFF_S until the upstream returns.
NETWORK_FAIL_THRESHOLD = 5
NETWORK_FAIL_BACKOFF_S = 300


def _short_err(e: BaseException) -> str:
    """Strip retry/exception wrappers down to a one-line root cause."""
    cur = e
    seen = 0
    while cur.__cause__ is not None and seen < 4:
        cur = cur.__cause__
        seen += 1
    return f"{type(cur).__name__}: {cur}"


# ---- WebSocket consumer (replaces polling) ---------------------------------


async def _live_ws_loop() -> None:
    """Long-running consumer of api-tennis's WebSocket. Replaces polling
    with push: sub-second match updates, lower bandwidth, and we don't
    burn through REST quota on data that hasn't changed.

    Each upstream message is treated like a single live-poll row — fed
    through `upsert_live_matches` → events → push fan-out, exactly the
    same downstream path the REST poll used. After every successful
    (re)connect we do one REST live-poll to seed any state that changed
    while we were disconnected.
    """
    if not settings.api_tennis_key or not settings.api_tennis_ws_url:
        log.info("live WS disabled — no API_TENNIS_KEY or ws_url")
        return

    # `websockets` is bundled by uvicorn[standard] so this import is free.
    import websockets

    backoff = 1
    while True:
        # Seed via REST. On a fresh boot this is the initial state load;
        # on reconnect this catches anything that changed during the gap.
        try:
            touched = await _poll_live_once()
            if touched:
                log.info("live WS seed: %d match(es) via REST", touched)
        except (RetryError, httpx.ConnectError, httpx.TimeoutException):
            pass  # tolerate REST being down too — WS may still work
        except Exception:
            log.exception("live WS REST seed failed (continuing to WS)")

        url = (
            f"{settings.api_tennis_ws_url}"
            f"?APIkey={settings.api_tennis_key}&timezone=UTC"
        )
        try:
            log.info("live WS connecting...")
            async with websockets.connect(url, ping_interval=30, ping_timeout=15) as ws:
                log.info("live WS connected")
                backoff = 1  # reset on success
                async for raw in ws:
                    try:
                        await _handle_ws_message(raw)
                    except Exception:
                        log.exception("live WS handler failed (continuing)")
        except Exception as e:
            log.warning(
                "live WS dropped: %s — reconnect in %ds",
                _short_err(e), backoff,
            )

        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 60)


async def _handle_ws_message(raw: str | bytes) -> None:
    """Parse one upstream message into LiveMatch(es) and run them through
    the same DB upsert + push fan-out pipeline as the polling path."""
    try:
        text = raw if isinstance(raw, str) else raw.decode("utf-8")
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
        return

    # Possible shapes from api-tennis WS:
    #   {"event_key": "...", ...}     — single match update
    #   [match1, match2, ...]         — initial-sync batch
    #   {"action": "ping"|...}        — control / heartbeat (ignored)
    rows: list[dict] = []
    if isinstance(data, dict) and "event_key" in data:
        rows = [data]
    elif isinstance(data, list):
        rows = [d for d in data if isinstance(d, dict) and "event_key" in d]
    else:
        return

    provider = get_live_provider()
    if provider.name != "api_tennis":
        return

    # ApiTennisProvider._map is the same row→LiveMatch mapper the REST
    # path uses, so we keep a single source of truth for the wire shape.
    matches = []
    for row in rows:
        try:
            matches.append(provider._map(row))  # type: ignore[attr-defined]
        except Exception:
            log.exception("live WS: map failed for row %s", str(row)[:120])
    if not matches:
        return

    api_ids = [lm.provider_match_id for lm in matches if lm.provider_match_id]
    with Session(engine) as session:
        _touched, events = upsert_live_matches(session, matches)
        # Same session reads the just-committed rows so we can ship MatchSummary
        # dicts to SSE subscribers — browsers render straight from the event
        # without a follow-up REST call.
        if api_ids:
            try:
                upserted = session.exec(
                    select(Match).where(Match.api_tennis_id.in_(api_ids))
                ).all()
                for m in upserted:
                    live_hub.publish({
                        "type": "match.updated",
                        "match": match_to_summary(session, m).model_dump(mode="json"),
                    })
            except Exception:
                log.exception("live WS hub publish failed")
    if events:
        try:
            await fan_out_match_events(events)
            await fan_out_follow_events(events)
        except Exception:
            log.exception("live WS event fan-out failed")


async def _poll_today() -> None:
    """Fetch the full day's schedule. Once an hour during play days, less when idle."""
    provider = get_live_provider()
    if provider.name == "noop":
        return
    try:
        today = await provider.fetch_today()
        if not today:
            return
        with Session(engine) as session:
            count, _events = upsert_live_matches(session, today)
        log.info("today poll: %d fixtures upserted", count)
    except Exception:
        log.exception("today poll failed")


async def _sync_news_job() -> None:
    try:
        with Session(engine) as session:
            new_items = sync_news(session)
            # Capture IDs while the session is open — handing the ORM
            # instances to fan-out across a session boundary raised
            # DetachedInstanceError because they're evicted on close.
            new_ids = [n.id for n in new_items if n.id is not None]
        if new_ids:
            log.info("news sync: %d new items", len(new_ids))
            try:
                delivered = await fan_out_news(new_ids)
                if delivered:
                    log.info("news fan-out: %d notifications", delivered)
            except Exception:
                log.exception("news fan-out failed")
    except Exception:
        log.exception("news sync failed")


def _sync_videos_job() -> None:
    """Pull each configured YouTube channel's RSS feed and persist new
    VideoItems. Sync, not async — feedparser is sync I/O and feeding it
    a thread executor is a future optimisation if it ever matters.
    """
    try:
        with Session(engine) as session:
            new_items = sync_videos(session)
        if new_items:
            log.info("video sync: %d new items", len(new_items))
    except Exception:
        log.exception("video sync failed")


async def _sync_rankings_job() -> None:
    """Pull current ATP + WTA standings and upsert into Player + Ranking."""
    provider = get_live_provider()
    if provider.name == "noop":
        return
    total = 0
    for tour in (Tour.ATP, Tour.WTA):
        try:
            entries = await provider.fetch_rankings(tour.value)
            with Session(engine) as session:
                inserted = upsert_rankings(session, entries)
            total += inserted
            log.info("rankings sync %s: %d new ranking rows (%d entries)",
                     tour.value, inserted, len(entries))
        except Exception:
            log.exception("rankings sync %s failed", tour.value)
    return total


def _recategorize_job() -> None:
    """One-shot tournament recategorization on boot."""
    try:
        with Session(engine) as session:
            changed = recategorize_all(session)
        if changed:
            log.info("recategorized %d tournaments", changed)
    except Exception:
        log.exception("recategorize failed")


async def _sync_catalog_job() -> None:
    """Pull every tournament brand the provider knows about."""
    provider = get_live_provider()
    if provider.name == "noop":
        return
    try:
        # First pass: clean up any prefixed-brand rows from earlier syncs.
        with Session(engine) as session:
            merged = cleanup_prefixed_brands(session)
        if merged:
            log.info("dedupe: collapsed %d prefixed brand rows", merged)

        items = await provider.fetch_tournaments()
        with Session(engine) as session:
            added, updated = upsert_catalog(session, items)
        log.info("catalog sync: %d added, %d updated (%d in feed)",
                 added, updated, len(items))
    except Exception:
        log.exception("catalog sync failed")


async def _enrich_tournaments_job() -> None:
    """Wikipedia blurbs + images for top-tier tournaments. Polite rate-limited.

    Batch sized for our scale — the tournament catalog is small, and the
    backlog drains over a few hourly runs rather than blasting through it
    all in one go.
    """
    try:
        with Session(engine) as session:
            enriched = await enrich_pending(session, max_count=50)
        if enriched:
            log.info("tournament enrich: %d updated", enriched)
    except Exception:
        log.exception("tournament enrich failed")


async def _enrich_tournament_dates_job() -> None:
    """Wikidata P580/P582 → Tournament.start_date/end_date. The formal-dates
    backfill the user wants — match-derived windows are flaky around
    overnight ingest gaps, but Wikidata dates are authoritative."""
    try:
        with Session(engine) as session:
            hits = await enrich_dates_pending(session, max_count=50)
        if hits:
            log.info("tournament dates: %d updated", hits)
    except Exception:
        log.exception("tournament dates enrich failed")


async def _enrich_player_socials_job() -> None:
    """Wikidata-sourced Instagram / X handles for the top 100 of each tour."""
    try:
        with Session(engine) as session:
            tried, ok = await enrich_players_socials(session, top_n=100)
        if tried:
            log.info("player socials: %d updated / %d tried", ok, tried)
    except Exception:
        log.exception("player socials enrich failed")


async def _enrich_player_bios_job() -> None:
    """Wikipedia bios for players with known Wikidata IDs.

    Runs after socials enrichment so the wikidata_id pool is freshly filled.
    Idempotent: skips players who already have a bio.
    """
    try:
        with Session(engine) as session:
            tried, ok = await enrich_players_bios(session, max_count=100)
        if tried:
            log.info("player bios: %d updated / %d tried", ok, tried)
    except Exception:
        log.exception("player bio enrich failed")


async def _scrape_draws_job() -> None:
    """Pull Wikipedia bracket structure for top-tier in-progress tournaments.

    Hourly cadence: draws change slowly (seeds locked at the draw ceremony,
    a couple of days before play), but we want the bracket to populate
    quickly once Wikipedia gets the draw. Per-tournament cost is one MediaWiki
    API call (cached for ~30s upstream) + a name-lookup pass.
    """
    try:
        updated = await scrape_pending_draws()
        if updated:
            log.info("wikipedia draws: updated %d match rows", updated)
    except Exception:
        log.exception("wikipedia draw scrape failed")


async def _healthchecks_ping_job() -> None:
    """Push heartbeat to Healthchecks.io. If they don't hear from us
    within their grace window they fire their configured webhook (on
    prod: the Vercel relay → Resend email)."""
    url = settings.healthchecks_ping_url
    if not url:
        return
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(url)
        if r.status_code >= 400:
            log.warning("healthchecks ping: HTTP %d", r.status_code)
    except Exception as e:
        log.warning("healthchecks ping failed: %s", e)


def _sweep_stuck_matches_job() -> None:
    """Repair matches the upstream forgot to close out.

    api-tennis occasionally drops a match's final status update — we end up
    with a row that has a partial score and `status='scheduled'` (or 'live')
    long after the match actually ended. Without this sweep, those rows
    show up in 'Upcoming' on the tournament page forever.

    Rules:
      - status='scheduled' AND scheduled_at older than SCHEDULED_STALE_H
        → status='cancelled' (we can't know if it was played, walked over,
          or just postponed and lost in the feed)
      - status='live' AND updated_at older than LIVE_STALE_H
        → status='finished' (we know it ended; we just don't know how)

    Conservative thresholds — match days run long, and being too eager
    would mis-flag an actual scheduled match that's just delayed.
    """
    from app.models.match import Match, MatchStatus

    SCHEDULED_STALE_H = 24
    LIVE_STALE_H = 6
    now = datetime.utcnow()
    scheduled_cutoff = now - timedelta(hours=SCHEDULED_STALE_H)
    live_cutoff = now - timedelta(hours=LIVE_STALE_H)

    try:
        cancelled_count = 0
        finished_count = 0
        with Session(engine) as session:
            stuck_scheduled = session.exec(
                select(Match).where(
                    Match.status == MatchStatus.SCHEDULED,
                    Match.scheduled_at.is_not(None),
                    Match.scheduled_at < scheduled_cutoff,
                )
            ).all()
            for m in stuck_scheduled:
                m.status = MatchStatus.CANCELLED
                m.updated_at = now
                session.add(m)
                cancelled_count += 1

            stuck_live = session.exec(
                select(Match).where(
                    Match.status == MatchStatus.LIVE,
                    Match.updated_at < live_cutoff,
                )
            ).all()
            for m in stuck_live:
                m.status = MatchStatus.FINISHED
                m.finished_at = m.finished_at or now
                m.updated_at = now
                session.add(m)
                finished_count += 1

            if cancelled_count or finished_count:
                session.commit()
                log.info(
                    "stuck-match sweep: cancelled %d scheduled (>%dh), finished %d live (>%dh)",
                    cancelled_count, SCHEDULED_STALE_H, finished_count, LIVE_STALE_H,
                )
    except Exception:
        log.exception("stuck-match sweep failed")


# ---- Lifecycle --------------------------------------------------------------


def start_scheduler() -> None:
    global _scheduler, _live_task
    if _scheduler:
        return
    _scheduler = AsyncIOScheduler()

    # Today fetch — refresh schedule hourly so the cadence loop has fresh data
    # to base its decisions on. Run once immediately on boot too.
    _scheduler.add_job(
        _poll_today,
        IntervalTrigger(hours=1),
        id="poll_today",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.add_job(
        _poll_today,
        DateTrigger(run_date=datetime.utcnow() + timedelta(seconds=2)),
        id="poll_today_boot",
    )

    # News
    _scheduler.add_job(
        _sync_news_job,
        IntervalTrigger(seconds=settings.news_poll_interval),
        id="sync_news",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.add_job(
        _sync_news_job,
        DateTrigger(run_date=datetime.utcnow() + timedelta(seconds=3)),
        id="sync_news_boot",
    )

    # Videos (YouTube highlight feeds). Same cadence as news — highlights
    # publish a few times per day during big tournaments.
    _scheduler.add_job(
        _sync_videos_job,
        IntervalTrigger(seconds=settings.news_poll_interval),
        id="sync_videos",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.add_job(
        _sync_videos_job,
        DateTrigger(run_date=datetime.utcnow() + timedelta(seconds=6)),
        id="sync_videos_boot",
    )

    # Rankings — daily at the configured hour, plus once at boot
    from apscheduler.triggers.cron import CronTrigger
    _scheduler.add_job(
        _sync_rankings_job,
        CronTrigger(hour=settings.rankings_sync_hour, minute=0),
        id="sync_rankings",
        max_instances=1,
        coalesce=True,
    )
    # Boot trigger removed — daily cadence is fine; a deploy doesn't change
    # rankings, and stacking 6+ enrichment jobs in the first 90 seconds was
    # the bulk of the boot-time connection-pool storm.

    # One-shot recategorize on every boot — cheap and self-correcting if the
    # classifier rules evolve.
    _scheduler.add_job(
        _recategorize_job,
        DateTrigger(run_date=datetime.utcnow() + timedelta(seconds=1)),
        id="recategorize_boot",
    )

    # Wikipedia bracket scraper. Hourly cadence — draws barely change once
    # locked in, but we want a fresh deploy to pick up the latest state
    # quickly. Boot trigger runs ~20s in so the WS consumer is already
    # seeded with matches the scraper can attach bracket info to.
    _scheduler.add_job(
        _scrape_draws_job,
        IntervalTrigger(hours=1),
        id="scrape_draws",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.add_job(
        _scrape_draws_job,
        DateTrigger(run_date=datetime.utcnow() + timedelta(seconds=20)),
        id="scrape_draws_boot",
    )

    # Stuck-match janitor — promote rows the WS forgot to close. Hourly is
    # plenty: it only fires when upstream silently dropped a status update,
    # which is rare. Also runs once shortly after boot so a fresh deploy
    # reconciles any stale rows that accumulated while we were off.
    _scheduler.add_job(
        _sweep_stuck_matches_job,
        IntervalTrigger(hours=1),
        id="sweep_stuck_matches",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.add_job(
        _sweep_stuck_matches_job,
        DateTrigger(run_date=datetime.utcnow() + timedelta(seconds=15)),
        id="sweep_stuck_matches_boot",
    )

    # Tournament catalog — the full brand list. Once at boot + daily.
    _scheduler.add_job(
        _sync_catalog_job,
        CronTrigger(hour=settings.rankings_sync_hour, minute=15),
        id="sync_catalog",
        max_instances=1,
        coalesce=True,
    )
    # Boot trigger removed — see sync_rankings_boot note.

    # Player socials (Wikidata) — weekly + on boot. Walks top 200 ATP/WTA;
    # one player every ~500ms so a full run takes ~3 min on cold start, and
    # the staleness window keeps re-runs cheap.
    _scheduler.add_job(
        _enrich_player_socials_job,
        IntervalTrigger(weeks=1),
        id="enrich_player_socials",
        max_instances=1,
        coalesce=True,
    )
    # Boot trigger removed — weekly cadence handles new players over time.

    # Player bios — runs ~30s after boot, after the socials job has had a
    # chance to populate wikidata_ids, then weekly.
    _scheduler.add_job(
        _enrich_player_bios_job,
        IntervalTrigger(weeks=1),
        id="enrich_player_bios",
        max_instances=1,
        coalesce=True,
    )
    # Boot trigger removed — weekly cadence is fine.

    # Tournament enrichment (Wikipedia blurbs + images) — runs after catalog
    # so there's something to enrich. Hourly sweep: each run handles up to 200
    # unenriched tournaments. enriched_at marks them processed.
    _scheduler.add_job(
        _enrich_tournaments_job,
        IntervalTrigger(hours=1),
        id="enrich_tournaments",
        max_instances=1,
        coalesce=True,
    )
    # Boot trigger removed — hourly cadence picks up new tournaments soon enough.

    # Tournament formal dates from Wikidata. Daily + once shortly after boot
    # so the first run after deploy backfills the live tier. Staggered after
    # the description enrichment so the two HTTP-heavy jobs don't overlap.
    _scheduler.add_job(
        _enrich_tournament_dates_job,
        IntervalTrigger(days=1),
        id="enrich_tournament_dates",
        max_instances=1,
        coalesce=True,
    )
    # Boot trigger removed — daily cadence is plenty.

    if settings.healthchecks_ping_url:
        _scheduler.add_job(
            _healthchecks_ping_job,
            IntervalTrigger(seconds=settings.healthchecks_interval),
            id="healthchecks_ping",
            max_instances=1,
            coalesce=True,
            # APScheduler's default 1-second misfire grace skipped pings
            # whenever the event loop stalled briefly (heavy request, GC
            # pause), causing false "DOWN" alerts. 120s means even a
            # genuinely slow few seconds still fires the ping — and a
            # ping that's a minute late is still a valid heartbeat, far
            # better than spurious alerts.
            misfire_grace_time=120,
        )
        # Fire one ping shortly after boot so a fresh deploy is reported
        # alive without waiting a full interval.
        _scheduler.add_job(
            _healthchecks_ping_job,
            DateTrigger(run_date=datetime.utcnow() + timedelta(seconds=10)),
            id="healthchecks_ping_boot",
            max_instances=1,
            coalesce=True,
        )

    _scheduler.start()

    # Live data comes via api-tennis WebSocket — sub-second updates
    # instead of 15s polling. The loop self-recovers (REST seed + WS
    # reconnect with exp backoff) when connection drops. If WS is
    # disabled (no key / no url), falls back silently — REST poll
    # still runs hourly via _poll_today for fixtures.
    _live_task = asyncio.get_event_loop().create_task(_live_ws_loop())

    log.info("scheduler started (live source: %s)",
             "ws" if settings.api_tennis_ws_url and settings.api_tennis_key else "polling-fallback")


def stop_scheduler() -> None:
    global _scheduler, _live_task
    if _live_task:
        _live_task.cancel()
        _live_task = None
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
