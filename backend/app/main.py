import asyncio
import logging
import resource
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    admin,
    digest,
    h2h,
    follows,
    match_follows,
    matches,
    news,
    players,
    push,
    rankings,
    search,
    spot_the_ball,
    stream,
    tournaments,
    videos,
)
from app.config import settings
from app.db.session import init_db
from app.jobs.scheduler import start_scheduler, stop_scheduler


# ---- Memory telemetry ------------------------------------------------------
#
# We were OOM-killed in production with no visibility into which requests
# were the culprits. These helpers + the middleware below log RSS deltas
# per request and a periodic snapshot, so `journalctl -u tennismob | grep
# 'rss='` shows what's eating memory.

req_log = logging.getLogger("app.requests")
mem_log = logging.getLogger("app.memory")

_in_flight = 0  # rough concurrency count (not lock-protected — close enough)


def _current_rss_kb() -> int:
    """Current resident set size in KB (Linux only via /proc)."""
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1])
    except OSError:
        pass
    return 0


def _peak_rss_kb() -> int:
    """High-water mark since process start. On Linux ru_maxrss is in KB."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss


def _disk_pct() -> int:
    """Free-space percentage on the root filesystem. Cheap stdlib check —
    accumulating journald + SQLite write-ahead-log can fill a small disk
    over days; we want to spot it before the box wedges."""
    try:
        import shutil
        total, _, free = shutil.disk_usage("/")
        return int((1 - free / total) * 100)
    except Exception:
        return -1


async def _memory_sampler() -> None:
    """Once a minute, log RSS + disk + concurrency + SSE subscriber count.
    Subscriber count surfaces SSE connection leaks (silently-half-open
    streams that accumulate behind buffering proxies); paired with RSS
    it's the fastest signal that the live hub is leaking."""
    from app.services.live_hub import hub as live_hub
    while True:
        try:
            await asyncio.sleep(60)
            mem_log.info(
                "rss=%dM peak=%dM disk=%d%% in_flight=%d sse=%d",
                _current_rss_kb() // 1024,
                _peak_rss_kb() // 1024,
                _disk_pct(),
                _in_flight,
                live_hub.subscriber_count,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            mem_log.exception("memory sampler iteration failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    sampler = asyncio.create_task(_memory_sampler())
    yield
    sampler.cancel()
    stop_scheduler()


app = FastAPI(
    title="Tennismob API",
    version="0.1.0",
    description="Fan-first tennis data — ATP/WTA live, players, tournaments, H2H, news.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_request_metrics(request: Request, call_next):
    """Log RSS + duration per /api request. Helps spot memory-heavy
    endpoints in journalctl. Heavy-request warning fires above 30 MB peak
    growth."""
    if not request.url.path.startswith("/api/"):
        return await call_next(request)

    global _in_flight
    _in_flight += 1
    peak_before = _peak_rss_kb()
    start = time.perf_counter()
    try:
        response = await call_next(request)
    finally:
        _in_flight -= 1

    duration_ms = (time.perf_counter() - start) * 1000
    peak_delta_kb = _peak_rss_kb() - peak_before
    rss_mb = _current_rss_kb() // 1024

    req_log.info(
        "%s %s %d %.0fms rss=%dM peak+%dK n=%d",
        request.method, request.url.path, response.status_code,
        duration_ms, rss_mb, peak_delta_kb, _in_flight + 1,
    )
    if peak_delta_kb > 30_000:
        req_log.warning(
            "memory-heavy request: %s %s peak+%dM",
            request.method, request.url.path, peak_delta_kb // 1024,
        )
    return response


# Cache-Control middleware. Vercel and any CDN in front of us will cache GET
# /api responses for these durations, dramatically reducing how often
# Vercel's renderer / browsers actually hit the box. `s-maxage` = CDN-only
# (browsers ignore), `stale-while-revalidate` lets the CDN serve a stale
# response instantly while it refreshes in the background.
#
# Order matters — most specific paths first.
_CACHE_RULES: list[tuple[str, int]] = [
    ("/api/matches/live", 10),       # heartbeat; revalidate fast
    ("/api/matches/today", 30),
    ("/api/matches/", 10),           # match-detail (could be live)
    ("/api/tournaments/index", 300), # ~5 min; sections flip when in_progress changes
    ("/api/news", 300),              # scheduler refreshes every 15 min
    ("/api/rankings", 1800),         # daily refresh upstream
    ("/api/h2h", 600),                # evergreen for any pair
    ("/api/search", 60),
]
# Path *contains* one of these → cache hard. These are aggregations over
# entire tournament histories — they almost never change.
_EVERGREEN_FRAGMENTS = ("/champions", "/overview", "/tournament-history")
# Per-tournament / per-player match LISTS — could include live matches,
# so keep the cache short. Matched via endsWith because the tournament
# detail endpoint shares the /api/tournaments/ prefix and we don't want
# the same TTL for it (the brand-level info is evergreen).
_LIVE_LIST_SUFFIX = "/matches"
_LIVE_LIST_TTL = 20
# Default for anything else under /api/ (player profile, tournament
# detail, etc.) — mostly static, refreshed during enrichment cycles.
_DEFAULT_CACHE_S = 60


@app.middleware("http")
async def add_cache_headers(request: Request, call_next):
    response = await call_next(request)
    if request.method != "GET" or response.status_code >= 400:
        return response
    path = request.url.path
    # User-specific endpoints — never cache at the CDN.
    if path.startswith(("/api/follows", "/api/push")):
        return response
    # SSE stream — never cache, never buffer.
    if path == "/api/stream":
        return response
    if not path.startswith("/api/"):
        return response
    # Endpoint-set Cache-Control wins.
    if any(k.lower() == "cache-control" for k in response.headers.keys()):
        return response

    s_maxage: int | None = None
    for prefix, ttl in _CACHE_RULES:
        if path.startswith(prefix):
            s_maxage = ttl
            break
    if s_maxage is None and path.endswith(_LIVE_LIST_SUFFIX):
        # /api/{tournaments,players}/.../matches — short TTL since live
        # matches surface here.
        s_maxage = _LIVE_LIST_TTL
    if s_maxage is None and any(frag in path for frag in _EVERGREEN_FRAGMENTS):
        s_maxage = 1800  # 30 min for evergreen historical aggregates
    if s_maxage is None:
        s_maxage = _DEFAULT_CACHE_S

    response.headers["Cache-Control"] = (
        f"public, s-maxage={s_maxage}, stale-while-revalidate={s_maxage * 4}"
    )
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(players.router)
app.include_router(tournaments.router)
app.include_router(matches.router)
app.include_router(rankings.router)
app.include_router(news.router)
app.include_router(h2h.router)
app.include_router(follows.router)
app.include_router(match_follows.router)
app.include_router(push.router)
app.include_router(search.router)
app.include_router(stream.router)
app.include_router(videos.router)
app.include_router(digest.router)
app.include_router(spot_the_ball.router)
app.include_router(admin.router)
