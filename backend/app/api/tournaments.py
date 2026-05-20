from collections import defaultdict
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, func, select

from app.api._helpers import match_to_summary, player_summary
from app.db.session import get_session
from app.models.match import Match, MatchStatus
from app.models.player import Player, Tour
from app.models.tournament import Tournament, TournamentCategory
from app.schemas.history import (
    LastEdition,
    TournamentChampion,
    TournamentOverview,
    TournamentRecord,
    TournamentStats,
)
from app.schemas.match import MatchSummary
from app.schemas.tournament import TournamentDetail, TournamentSummary
from app.services.categorize import tier_weight
from app.services.rounds import round_depth
from app.services.tournament_resolver import BRAND_ALIASES

# Inverted alias map — built once at module load. URL handlers consult
# this so a bookmark to an alias slug (e.g. /tournaments/atp/french-open)
# still resolves to the canonical brand row after merge.
_ALIAS_TO_CANONICAL: dict[str, str] = {}
for _c, _aliases in BRAND_ALIASES.items():
    for _a in _aliases:
        _ALIAS_TO_CANONICAL[_a] = _c


def _canonical_url_slug(slug: str) -> str:
    """Map a request's brand slug through the alias table.
    Returns the canonical brand slug used in the DB."""
    return _ALIAS_TO_CANONICAL.get(slug, slug)

router = APIRouter(prefix="/api/tournaments", tags=["tournaments"])


@router.get("", response_model=list[TournamentSummary])
def list_tournaments(
    tour: Tour | None = None,
    year: int | None = None,
    upcoming: bool = False,
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    stmt = select(Tournament)
    if tour:
        stmt = stmt.where(Tournament.tour == tour)
    if year:
        stmt = stmt.where(Tournament.year == year)
    if upcoming:
        stmt = stmt.where(Tournament.start_date >= date.today())
    stmt = stmt.order_by(Tournament.start_date.desc()).limit(limit)
    rows = session.exec(stmt).all()
    return [TournamentSummary(**t.model_dump()) for t in rows]


# ---- Index page payload ----------------------------------------------------


class IndexTournament(BaseModel):
    slug: str
    year: int
    name: str
    tour: Tour
    category: TournamentCategory
    surface: str | None = None
    city: str | None = None
    country_code: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    image_url: str | None = None
    live_count: int = 0
    today_count: int = 0
    is_in_progress: bool = False
    # All tours that share this brand at the same tier-pair (e.g. ATP+WTA Slams).
    # `tour` above is the primary; `tours` lets the client pick by user preference.
    tours: list[str] = []
    # Description blurbs are intentionally NOT included here — at ~150–500 chars
    # × every tournament in the catalog, they push the index response past 2 MB
    # and break Next.js ISR caching. The detail endpoint serves the full blurb
    # when the user opens a card.


class IndexSection(BaseModel):
    key: str  # e.g. "live", "grand_slam", "atp_1000"
    title: str
    tournaments: list[IndexTournament]
    # `total` lets the client know whether to offer "load more" — even when
    # we cap `tournaments` to a single page, the catalog can have hundreds
    # of historic ITF / Challenger editions in the same tier.
    total: int


class IndexResponse(BaseModel):
    sections: list[IndexSection]


# Tunable. 30 covers the common case (Grand Slams, 1000s, 500s — none have
# more than ~12 brand cards) and gives Challengers/ITF a reasonable first
# page without choking RN's layout pass.
INDEX_PAGE_SIZE = 30


_CATEGORY_LABELS: dict[TournamentCategory, str] = {
    TournamentCategory.GRAND_SLAM: "Grand Slams",
    TournamentCategory.ATP_FINALS: "ATP Finals",
    TournamentCategory.WTA_FINALS: "WTA Finals",
    TournamentCategory.ATP_1000: "ATP Masters 1000",
    TournamentCategory.WTA_1000: "WTA 1000",
    TournamentCategory.ATP_500: "ATP 500",
    TournamentCategory.WTA_500: "WTA 500",
    TournamentCategory.ATP_250: "ATP 250",
    TournamentCategory.WTA_250: "WTA 250",
    TournamentCategory.DAVIS_CUP: "Davis Cup",
    TournamentCategory.BJK_CUP: "Billie Jean King Cup",
    TournamentCategory.CHALLENGER: "Challenger Tour",
    TournamentCategory.ITF: "ITF World Tour",
    TournamentCategory.OTHER: "Other",
}


# Categories that pair across tours — slugs colliding inside one of these
# pairs is a real joint event (Australian Open, Indian Wells, Madrid, etc.)
# and gets collapsed to one card. Slugs colliding across a non-pair (e.g. a
# men's Challenger and a women's ITF that happen to share a city name) stay
# as two separate cards because they aren't actually the same tournament.
_TIER_PAIRS: list[set[TournamentCategory]] = [
    {TournamentCategory.GRAND_SLAM},
    {TournamentCategory.ATP_FINALS, TournamentCategory.WTA_FINALS},
    {TournamentCategory.ATP_1000, TournamentCategory.WTA_1000},
    {TournamentCategory.ATP_500, TournamentCategory.WTA_500},
    {TournamentCategory.ATP_250, TournamentCategory.WTA_250},
    {TournamentCategory.DAVIS_CUP, TournamentCategory.BJK_CUP},
]


def _is_paired_group(items: list[IndexTournament]) -> bool:
    """True if every item's category fits inside a single tier-pair set."""
    if len(items) < 2:
        return False
    cats = {i.category for i in items}
    return any(cats.issubset(pair) for pair in _TIER_PAIRS)


def _collapse_joint_brands(items: list[IndexTournament]) -> list[IndexTournament]:
    """Dedup `Australian Open ATP` + `Australian Open WTA` into one card,
    aggregating live/today counts and exposing both `tours` for the client
    to pick from. Picks ATP as primary by default — frontend swaps based on
    the user's preferred-tour setting.
    """
    by_slug: dict[str, list[IndexTournament]] = defaultdict(list)
    for i in items:
        by_slug[i.slug].append(i)

    out: list[IndexTournament] = []
    for slug, group in by_slug.items():
        if not _is_paired_group(group):
            out.extend(group)
            continue

        # Primary: prefer in-progress, then more activity, then alphabetical
        # tour (so atp wins tiebreaks, matching the default preference).
        primary = sorted(
            group,
            key=lambda x: (
                0 if x.is_in_progress else 1,
                -x.live_count,
                -x.today_count,
                x.tour.value,
            ),
        )[0]
        primary.live_count = sum(x.live_count for x in group)
        primary.today_count = sum(x.today_count for x in group)
        primary.is_in_progress = any(x.is_in_progress for x in group)
        primary.tours = sorted({x.tour.value for x in group})
        out.append(primary)
    return out


def _compute_index_sections(session: Session) -> list[tuple[str, str, list[IndexTournament]]]:
    """All the heavy lifting for tournaments-index.

    Returns sections in display order as a list of `(key, title, items)`.
    Used by both `/index` (pages) and `/sections/{key}` (paginated load
    of a single section).

    Dedupe rule: one card per (slug, tour). When the same brand has multiple
    rows (e.g. Wimbledon 2025 with results + Wimbledon 2026 placeholder), we
    prefer the row with active fixtures, falling back to the most recent year.
    "Happening now" includes any tournament whose match window covers today —
    not just events with matches actively in progress this minute. That way a
    multi-day event stays pinned during overnight breaks and rest days.
    """
    today = date.today()
    today_start = datetime.combine(today, time.min)
    today_end = datetime.combine(today, time.max)

    # Per-tournament aggregates. Suspended matches count as "live"
    # for surfacing — they're an ongoing match, just paused.
    live_counts = dict(
        session.exec(
            select(Match.tournament_id, func.count(Match.id))
            .where(Match.status.in_([MatchStatus.LIVE, MatchStatus.SUSPENDED]))
            .group_by(Match.tournament_id)
        ).all()
    )
    today_counts = dict(
        session.exec(
            select(Match.tournament_id, func.count(Match.id))
            .where(Match.scheduled_at >= today_start, Match.scheduled_at <= today_end)
            .group_by(Match.tournament_id)
        ).all()
    )

    # "In progress" needs to be robust — Rome was disappearing from the live
    # section despite being mid-tournament because the original logic relied
    # *only* on a derived match-day window, which fails in three real-world
    # cases:
    #   (a) live matches with NULL scheduled_at (api-tennis sometimes omits
    #       event_time on in-play rows) get filtered out of the window query;
    #   (b) overnight gap when today's fixtures haven't been ingested yet —
    #       window's `last` is yesterday, today falls outside the range;
    #   (c) formal start_date / end_date fields, where populated, are the
    #       actual source of truth and were being ignored entirely.
    #
    # New rule: a tournament is in_progress if ANY of these hold.

    # Match-day window per tournament (matches with non-null scheduled_at).
    match_windows = session.exec(
        select(
            Match.tournament_id,
            func.min(Match.scheduled_at),
            func.max(Match.scheduled_at),
        )
        .where(Match.scheduled_at.is_not(None))
        .group_by(Match.tournament_id)
    ).all()
    has_match_ids = {tid for (tid, _, _) in match_windows}

    in_progress_ids: set[int] = set()

    # (1) Has at least one live match right this instant. Most authoritative
    # signal — by definition a tournament with a live match is in progress,
    # regardless of date logic.
    in_progress_ids.update(tid for tid, c in live_counts.items() if c > 0)

    # (2) Has matches scheduled today. Catches tournaments where the live
    # match's scheduled_at was NULL but other today-matches exist.
    in_progress_ids.update(tid for tid, c in today_counts.items() if c > 0)

    # (3) Match-day window covers today, with a 1-day grace at the *end*
    # of the window so an overnight ingest gap (today's fixtures haven't
    # synced in yet at 04:00 UTC) doesn't drop the tournament. Larger grace
    # creates false positives for tournaments that ended a few days ago.
    grace = timedelta(days=1)
    for tid, first, last in match_windows:
        if first is None or last is None:
            continue
        if first <= today_end and (last + grace) >= today_start:
            in_progress_ids.add(tid)

    # (4) Formal start_date AND end_date — both required. Earlier we used
    # `start_date + 21 days` as a fallback when end_date was missing, but
    # that kept Madrid 2026 visible for three weeks after it actually ended,
    # because Wikipedia prose extraction had only caught the start date.
    formal = session.exec(
        select(Tournament.id, Tournament.start_date, Tournament.end_date)
        .where(Tournament.start_date.is_not(None))
        .where(Tournament.end_date.is_not(None))
    ).all()
    for tid, start, end in formal:
        if start is None or end is None:
            continue
        if start <= today <= end:
            in_progress_ids.add(tid)

    # (5) "Singles final has been played, AND was >36 h ago" override —
    # authoritative "done" signal. Same rule as the per-match "today's
    # finished matches stay visible" treatment: we want a tournament
    # whose final ended this morning to still appear in the live
    # section through end-of-day so users can browse the day's
    # results without digging into the bracket. 36h is generous
    # enough to cover any client timezone; the client narrows
    # individual matches further to its local today.
    #
    # MUST filter is_doubles=False. Doubles finals often finish hours
    # earlier on the same day as the singles final and share the round
    # label ("ATP Rome - Final"); without this filter Rome dropped out
    # of "live" the moment its doubles final ended, even while singles
    # was mid-set.
    recent_final_cutoff = datetime.utcnow() - timedelta(hours=36)
    finished_finals = session.exec(
        select(Match.tournament_id).distinct()
        .where(Match.status == MatchStatus.FINISHED)
        .where(Match.is_doubles == False)  # noqa: E712 — SQLAlchemy expr
        .where((Match.round == "F") | Match.round.ilike("%final"))
        .where(func.coalesce(Match.finished_at, Match.scheduled_at) < recent_final_cutoff)
    ).all()
    in_progress_ids -= set(finished_finals)

    rows: list[Tournament] = session.exec(select(Tournament)).all()

    # Dedupe (slug, tour) → prefer the in-progress row, then any row with
    # matches, then most recent year. Without the in-progress preference,
    # a placeholder Wimbledon 2026 (no matches) would beat Wimbledon 2025
    # (with results) on year, and the card would link to a blank page.
    def rank(t: Tournament) -> tuple[int, int, int]:
        return (
            0 if t.id in in_progress_ids else 1,
            0 if t.id in has_match_ids else 1,
            -t.year,
        )

    by_series: dict[tuple[str, Tour], Tournament] = {}
    for t in rows:
        key = (t.slug, t.tour)
        cur = by_series.get(key)
        if cur is None or rank(t) < rank(cur):
            by_series[key] = t

    def to_index(t: Tournament) -> IndexTournament:
        return IndexTournament(
            slug=t.slug, year=t.year, name=t.name, tour=t.tour, category=t.category,
            surface=t.surface, city=t.city, country_code=t.country_code,
            start_date=t.start_date, end_date=t.end_date,
            image_url=t.image_url,
            live_count=live_counts.get(t.id, 0),
            today_count=today_counts.get(t.id, 0),
            is_in_progress=t.id in in_progress_ids,
            tours=[t.tour.value],
        )

    items = [to_index(t) for t in by_series.values()]
    items = _collapse_joint_brands(items)

    # "Happening now": any tournament currently in its date window, not just
    # those with live matches this instant. Order by current activity first
    # (live matches > today's count > tier > name).
    # Tier *always* trumps activity: a Grand Slam with 0 matches in play this
    # second still outranks a Challenger with 5 simultaneous live matches.
    # Within the same tier we then break ties on current activity (live > today)
    # and finally alphabetically for stability.
    live_section = sorted(
        (i for i in items if i.is_in_progress),
        key=lambda i: (tier_weight(i.category), -i.live_count, -i.today_count, i.name),
    )

    out: list[tuple[str, str, list[IndexTournament]]] = []
    if live_section:
        out.append(("live", "Happening now", live_section))

    grouped: dict[TournamentCategory, list[IndexTournament]] = defaultdict(list)
    for i in items:
        grouped[i.category].append(i)

    for cat in sorted(grouped.keys(), key=tier_weight):
        if cat == TournamentCategory.OTHER:
            continue
        cat_items = sorted(grouped[cat], key=lambda i: (-(i.today_count), i.name))
        out.append((cat.value, _CATEGORY_LABELS.get(cat, cat.value), cat_items))
    return out


# In-process cache for the heavy `_compute_index_sections` query. Under
# load the index endpoint runs alongside the WS consumer's ORM writes
# and gets starved on the asyncio event loop, taking 40+ seconds at the
# tail end. A short TTL keeps the data fresh enough (live_count /
# today_count change minute-to-minute, not second-to-second) while
# letting every burst of concurrent requests reuse the same compute.
_INDEX_CACHE: dict[str, object] = {"sections": None, "expires_at": 0.0}
_INDEX_CACHE_TTL = 30.0  # seconds


def _cached_index_sections(session: Session) -> list[tuple[str, str, list[IndexTournament]]]:
    import time
    now = time.monotonic()
    if _INDEX_CACHE["sections"] is not None and _INDEX_CACHE["expires_at"] > now:
        return _INDEX_CACHE["sections"]  # type: ignore[return-value]
    sections = _compute_index_sections(session)
    _INDEX_CACHE["sections"] = sections
    _INDEX_CACHE["expires_at"] = now + _INDEX_CACHE_TTL
    return sections


@router.get("/index", response_model=IndexResponse)
def tournaments_index(session: Session = Depends(get_session)) -> IndexResponse:
    """Tournament hub. Each section returns its first page; clients pull
    additional pages from /sections/{key}?offset=… on scroll."""
    raw = _cached_index_sections(session)
    return IndexResponse(sections=[
        IndexSection(
            key=k, title=title,
            tournaments=items[:INDEX_PAGE_SIZE],
            total=len(items),
        )
        for k, title, items in raw
    ])


@router.get("/sections/{key}", response_model=IndexSection)
def tournaments_section(
    key: str,
    offset: int = 0,
    limit: int = INDEX_PAGE_SIZE,
    session: Session = Depends(get_session),
) -> IndexSection:
    """Paginated load of one section, used by infinite-scroll on the
    mobile tournaments screen. Same sort + dedupe rules as /index."""
    if offset < 0:
        offset = 0
    limit = max(1, min(limit, 60))
    for k, title, items in _cached_index_sections(session):
        if k == key:
            return IndexSection(
                key=k, title=title,
                tournaments=items[offset:offset + limit],
                total=len(items),
            )
    raise HTTPException(status_code=404, detail="Unknown section")


@router.get("/{tour}/{slug}/champions", response_model=list[TournamentChampion])
def tournament_champions(
    tour: Tour,
    slug: str,
    limit: int = Query(5, ge=1, le=50),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    """One row per year, most recent first: just the year + the title winner.

    Memory-conscious: pulls only the columns we need (no full ORM hydration),
    caps the number of years walked, and breaks the moment we have enough.
    Concurrent requests during a Vercel build used to allocate ~150k Match
    ORM objects collectively which OOM-killed the service; this version
    allocates ~50× less per request. Walks newest-first.

    Registered ABOVE the `{tour}/{slug}/{year}` route so FastAPI doesn't try
    to parse "champions" as an int year.
    """
    slug = _canonical_url_slug(slug)
    needed = limit + offset
    # Buffer for years that have no F-round match in our DB (incomplete
    # Sackmann coverage, ongoing edition, walkover-only final, etc.)
    walk_buffer = 5

    instances = session.exec(
        select(Tournament.id, Tournament.year)
        .where(Tournament.tour == tour, Tournament.slug == slug)
        .order_by(Tournament.year.desc())
        .limit(needed + walk_buffer)
    ).all()
    if not instances:
        return []

    out: list[TournamentChampion] = []
    for tid, tyear in instances:
        if len(out) >= needed:
            break
        # Two-column tuples instead of full Match rows. Singles only —
        # the doubles final shares "Final" depth with the singles final
        # and (without this filter) max() can return the doubles winner,
        # which is how "Bolelli/Vavassori" briefly showed up as the 2026
        # Rome champion.
        rows = session.exec(
            select(Match.round, Match.winner_id)
            .where(
                Match.tournament_id == tid,
                Match.status == MatchStatus.FINISHED,
                Match.is_doubles == False,  # noqa: E712 — SQLAlchemy expr
            )
        ).all()
        if not rows:
            continue
        deepest_round, winner_id = max(rows, key=lambda r: round_depth(r[0]))
        if round_depth(deepest_round) < 100:
            continue
        if winner_id is None:
            continue
        champion = session.get(Player, winner_id)
        if not champion:
            continue
        out.append(TournamentChampion(year=tyear, champion=player_summary(champion)))

    return out[offset : offset + limit]


@router.get("/{tour}/{slug}/overview", response_model=TournamentOverview)
def tournament_overview(tour: Tour, slug: str, session: Session = Depends(get_session)):
    """Per-brand evergreen content: last final, records, at-a-glance stats.

    Aggregates across every year of (slug, tour). Memory-conscious:

      * Both Tournament and Match are pulled as lean column tuples — no
        full ORM hydration.
      * Matches are pre-grouped by tournament_id once so per-instance
        filtering is O(1) instead of O(N×M).
      * Player lookups go through a per-request cache, so the same
        winner isn't fetched repeatedly across the records computations.
    """
    slug = _canonical_url_slug(slug)
    instances = session.exec(
        select(
            Tournament.id, Tournament.year, Tournament.start_date,
            Tournament.draw_size, Tournament.prize_money,
            Tournament.surface, Tournament.indoor,
        )
        .where(Tournament.tour == tour, Tournament.slug == slug)
        .order_by(Tournament.year.desc())
    ).all()
    if not instances:
        return TournamentOverview(stats=TournamentStats())

    tids = [t.id for t in instances]
    year_by_tid = {t.id: t.year for t in instances}

    # Lean match rows — six columns, not the full 20+ field Match ORM.
    # Singles only: every "last edition" / "titles" / "appearances"
    # computation downstream assumes singles. Doubles "Final" rows would
    # otherwise crash into the singles Final at the same round_depth.
    matches = session.exec(
        select(
            Match.tournament_id, Match.round,
            Match.player1_id, Match.player2_id,
            Match.winner_id, Match.score,
        ).where(
            Match.tournament_id.in_(tids),
            Match.is_doubles == False,  # noqa: E712 — SQLAlchemy expr
        )
    ).all()

    # Pre-group so we don't re-scan all matches for each instance.
    matches_by_tid: dict[int, list] = defaultdict(list)
    for m in matches:
        matches_by_tid[m.tournament_id].append(m)

    # Per-request Player cache — the records computations call this with
    # the same pid from multiple paths (record card + country aggregate +
    # age comparison). One DB hit per unique winner is enough.
    player_cache: dict[int, Player | None] = {}

    def get_player(pid: int | None) -> Player | None:
        if pid is None:
            return None
        if pid not in player_cache:
            player_cache[pid] = session.get(Player, pid)
        return player_cache[pid]

    # ---- Last edition (most recent year with a Final) ----
    last_edition: LastEdition | None = None
    for t in instances:
        tmatches = matches_by_tid.get(t.id, [])
        finals = [m for m in tmatches if round_depth(m.round) >= 100]
        if not finals:
            continue
        f = max(finals, key=lambda m: round_depth(m.round))
        if f.winner_id is None:
            continue
        champ = get_player(f.winner_id)
        loser_id = f.player2_id if f.player1_id == f.winner_id else f.player1_id
        runner = get_player(loser_id)
        if champ:
            last_edition = LastEdition(
                year=t.year,
                champion=player_summary(champ),
                runner_up=player_summary(runner) if runner else None,
                final_score=f.score,
            )
            break

    # ---- Records (titles, appearances, oldest/youngest, country) ----
    titles_by_player: dict[int, set[int]] = defaultdict(set)
    apps_by_player: dict[int, set[int]] = defaultdict(set)
    titles_by_country: dict[str, int] = defaultdict(int)

    for m in matches:
        year = year_by_tid.get(m.tournament_id)
        if not year:
            continue
        if m.player1_id:
            apps_by_player[m.player1_id].add(year)
        if m.player2_id:
            apps_by_player[m.player2_id].add(year)
        if round_depth(m.round) >= 100 and m.winner_id is not None:
            titles_by_player[m.winner_id].add(year)

    records: list[TournamentRecord] = []

    def _record_for_player(p: Player | None, title: str, detail: str) -> TournamentRecord | None:
        if not p:
            return None
        return TournamentRecord(
            title=title,
            value=p.full_name,
            detail=detail,
            player_slug=p.slug,
            image_url=p.image_url or None,
            country_code=p.country_code,
        )

    if titles_by_player:
        top_id = max(titles_by_player, key=lambda i: len(titles_by_player[i]))
        n = len(titles_by_player[top_id])
        rec = _record_for_player(
            get_player(top_id), "Most titles", f"{n} title{'s' if n != 1 else ''}"
        )
        if rec:
            records.append(rec)

        # Country with the most titles via winners (uses the player cache).
        for pid in titles_by_player:
            p = get_player(pid)
            if p and p.country_code:
                titles_by_country[p.country_code] += len(titles_by_player[pid])
        if titles_by_country:
            top_country = max(titles_by_country, key=titles_by_country.get)
            records.append(
                TournamentRecord(
                    title="Most successful country",
                    value=top_country,
                    detail=f"{titles_by_country[top_country]} titles",
                    country_code=top_country,
                )
            )

        # Youngest + oldest champion (age in tournament year — coarse but stable).
        ages_at_title: list[tuple[int, int, int]] = []  # (player_id, year, age_at_year_start)
        for pid, years in titles_by_player.items():
            p = get_player(pid)
            if not p or not p.birth_date:
                continue
            for yr in years:
                ages_at_title.append((pid, yr, yr - p.birth_date.year))
        if ages_at_title:
            youngest = min(ages_at_title, key=lambda x: x[2])
            oldest = max(ages_at_title, key=lambda x: x[2])
            yp = get_player(youngest[0])
            op = get_player(oldest[0])
            if yp:
                records.append(
                    TournamentRecord(
                        title="Youngest champion",
                        value=yp.full_name,
                        detail=f"Age {youngest[2]}, {youngest[1]}",
                        player_slug=yp.slug,
                        image_url=yp.image_url or None,
                        country_code=yp.country_code,
                    )
                )
            if op and (yp is None or op.id != yp.id):
                records.append(
                    TournamentRecord(
                        title="Oldest champion",
                        value=op.full_name,
                        detail=f"Age {oldest[2]}, {oldest[1]}",
                        player_slug=op.slug,
                        image_url=op.image_url or None,
                        country_code=op.country_code,
                    )
                )

    if apps_by_player:
        top_id = max(apps_by_player, key=lambda i: len(apps_by_player[i]))
        n = len(apps_by_player[top_id])
        rec = _record_for_player(
            get_player(top_id), "Most appearances", f"{n} editions",
        )
        if rec:
            records.append(rec)

    # ---- Stats ----
    tids_with_finals = {
        m.tournament_id for m in matches if round_depth(m.round) >= 100
    }
    tids_with_data = set(matches_by_tid.keys())
    years_with_data = [year_by_tid[tid] for tid in tids if tid in tids_with_data]
    most_recent = next(
        (t for t in instances if t.id in tids_with_data), instances[0]
    )
    typical_month = most_recent.start_date.month if most_recent.start_date else None

    stats = TournamentStats(
        first_held=min(years_with_data) if years_with_data else None,
        total_editions=len(tids_with_finals),
        typical_month=typical_month,
        draw_size=most_recent.draw_size,
        prize_money=most_recent.prize_money,
        surface=most_recent.surface,
        indoor=most_recent.indoor,
    )

    return TournamentOverview(last_edition=last_edition, records=records, stats=stats)


def _resolve_current_edition(
    session: Session, tour: Tour, slug: str,
) -> Tournament | None:
    """Pick the most relevant Tournament row for (tour, slug).
    Callers can pass either the canonical brand slug or any registered
    alias — the resolver canonicalises before querying.

    Priority order:
      1. An edition with at least one live match.
      2. An edition whose formal start_date..end_date covers today.
      3. An edition with upcoming scheduled matches in the future.
      4. The most recent edition by year (most likely a recently
         completed one).

    Returns None if no editions exist for this brand at all.
    """
    slug = _canonical_url_slug(slug)
    rows = session.exec(
        select(Tournament)
        .where(Tournament.tour == tour, Tournament.slug == slug)
        .order_by(Tournament.year.desc())
    ).all()
    if not rows:
        return None

    tids = [t.id for t in rows if t.id is not None]
    if not tids:
        return rows[0]

    now = datetime.utcnow()
    today = date.today()

    # Aggregate match presence per tournament in one query each.
    # SQLModel's session.exec() unwraps single-column selects to scalars,
    # so the result is a list[int], not list[Row].
    live_tids: set[int] = set(
        session.exec(
            select(Match.tournament_id).distinct().where(
                Match.status.in_([MatchStatus.LIVE, MatchStatus.SUSPENDED]),
                Match.tournament_id.in_(tids),
            )
        ).all()
    )
    upcoming_tids: set[int] = set(
        session.exec(
            select(Match.tournament_id).distinct().where(
                Match.status == MatchStatus.SCHEDULED,
                Match.scheduled_at.is_not(None),
                Match.scheduled_at >= now,
                Match.tournament_id.in_(tids),
            )
        ).all()
    )

    for t in rows:
        if t.id in live_tids:
            return t
    for t in rows:
        if t.start_date and t.end_date and t.start_date <= today <= t.end_date:
            return t
    for t in rows:
        if t.id in upcoming_tids:
            return t
    return rows[0]


@router.get("/{tour}/{slug}", response_model=TournamentDetail)
def get_tournament_current(
    tour: Tour, slug: str, session: Session = Depends(get_session)
):
    """Year-less tournament detail. Resolves to the most relevant edition
    (live > in-progress > upcoming > most-recent) so a stable URL always
    surfaces the right content."""
    t = _resolve_current_edition(session, tour, slug)
    if not t:
        raise HTTPException(404, "Tournament not found")
    siblings = session.exec(
        select(Tournament).where(Tournament.slug == slug, Tournament.year == t.year)
    ).all()
    available = sorted({s.tour.value for s in siblings})
    return TournamentDetail(**t.model_dump(), available_tours=available)


@router.get("/{tour}/{slug}/matches", response_model=list[MatchSummary])
def tournament_matches_current(
    tour: Tour,
    slug: str,
    status: str | None = None,
    limit: int = Query(200, ge=1, le=500),
    session: Session = Depends(get_session),
):
    """Matches for the current edition. Same resolution rules as the
    year-less detail endpoint above."""
    t = _resolve_current_edition(session, tour, slug)
    if not t:
        raise HTTPException(404, "Tournament not found")
    stmt = select(Match).where(Match.tournament_id == t.id)
    if status:
        from app.api._helpers import filter_status
        stmt = filter_status(stmt, status)
    stmt = stmt.order_by(Match.scheduled_at).limit(limit)
    return [match_to_summary(session, m) for m in session.exec(stmt).all()]


# Year-specific matches endpoint — used by ChampionsList's lazy bracket
# fetch (the rest of the year-aware UI is gone, this hangs on for that
# one purpose).
@router.get("/{tour}/{slug}/{year}/matches", response_model=list[MatchSummary])
def tournament_matches(
    tour: Tour,
    slug: str,
    year: int,
    status: str | None = None,
    limit: int = Query(200, ge=1, le=500),
    session: Session = Depends(get_session),
):
    slug = _canonical_url_slug(slug)
    t = session.exec(
        select(Tournament).where(
            Tournament.tour == tour, Tournament.slug == slug, Tournament.year == year
        )
    ).first()
    if not t:
        raise HTTPException(404, "Tournament not found")
    stmt = select(Match).where(Match.tournament_id == t.id)
    if status:
        from app.api._helpers import filter_status
        stmt = filter_status(stmt, status)
    stmt = stmt.order_by(Match.scheduled_at).limit(limit)
    return [match_to_summary(session, m) for m in session.exec(stmt).all()]


