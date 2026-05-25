import asyncio
from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, or_, select

from app.api._helpers import match_to_summary
from app.db.session import get_session
from app.models.match import Match, MatchStatus
from app.models.player import Player, Tour
from app.models.ranking import Ranking
from app.models.tournament import Tournament
from app.schemas.history import TournamentHistoryEntry
from app.schemas.match import MatchSummary
from app.schemas.player import PlayerDetail, PlayerSummary
from app.schemas.player_snapshot import (
    PlayerSnapshot,
    SnapshotTitle,
    SurfaceRecord,
)
from app.services.player_enrich import enrich_one
from app.services.rounds import compute_player_result, round_depth

router = APIRouter(prefix="/api/players", tags=["players"])


@router.get("", response_model=list[PlayerSummary])
def list_players(
    tour: Tour | None = None,
    q: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    stmt = select(Player)
    if tour:
        stmt = stmt.where(Player.tour == tour)
    if q:
        stmt = stmt.where(Player.full_name.ilike(f"%{q}%"))
    stmt = stmt.order_by(Player.current_rank.is_(None), Player.current_rank).limit(limit)
    rows = session.exec(stmt).all()
    return [
        PlayerSummary(
            slug=p.slug, full_name=p.full_name, tour=p.tour,
            country_code=p.country_code, current_rank=p.current_rank, image_url=p.image_url,
        )
        for p in rows
    ]


@router.get("/{slug}", response_model=PlayerDetail)
async def get_player(slug: str, session: Session = Depends(get_session)):
    p = session.exec(select(Player).where(Player.slug == slug)).first()
    if not p:
        raise HTTPException(404, "Player not found")

    # Lazy enrichment: first visit to a player page triggers a get_players call
    # to fetch image / country / birth_date. Capped to 2s so we don't slow the
    # response if the upstream is sluggish; the data lands for the next visit.
    if p.image_url is None and p.api_tennis_id:
        try:
            await asyncio.wait_for(enrich_one(session, p), timeout=2.0)
        except asyncio.TimeoutError:
            pass
        # Re-read in case enrichment committed updates
        session.refresh(p)

    return PlayerDetail(
        slug=p.slug, full_name=p.full_name, tour=p.tour,
        country_code=p.country_code, current_rank=p.current_rank,
        image_url=(p.image_url or None),  # collapse "" → None for the JSON shape
        first_name=p.first_name, last_name=p.last_name, birth_date=p.birth_date,
        height_cm=p.height_cm, plays=p.plays, turned_pro=p.turned_pro,
        career_high_rank=p.career_high_rank, bio=p.bio,
        wikipedia_url=p.wikipedia_url,
        instagram_handle=p.instagram_handle,
        twitter_handle=p.twitter_handle,
        instagram_latest_post_url=p.instagram_latest_post_url,
    )


@router.get("/{slug}/matches", response_model=list[MatchSummary])
def player_matches(
    slug: str,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    p = session.exec(select(Player).where(Player.slug == slug)).first()
    if not p:
        raise HTTPException(404, "Player not found")
    base = (Match.player1_id == p.id) | (Match.player2_id == p.id)
    status_filter = None
    if status:
        from app.api._helpers import filter_status
        # filter_status is a query-decorator; we use it as a where-clause
        # extractor here by building a tmp stmt, but the simpler thing
        # is to just inline the SCHEDULED/LIVE case below since that's
        # the only one that matters for the NULL-fallback path.
        status_filter = status

    # Query A: matches with a real scheduled_at. SQL ORDER BY is reliable
    # here, so we cap to a modest buffer.
    stmt_a = select(Match).where(base, Match.scheduled_at.is_not(None))
    if status_filter:
        from app.api._helpers import filter_status
        stmt_a = filter_status(stmt_a, status_filter)
    rows_dated = session.exec(
        stmt_a.order_by(Match.scheduled_at.desc()).limit(limit * 4)
    ).all()

    # Query B: matches with NULL scheduled_at that should still be
    # surfaced — upcoming draws where api-tennis published the bracket
    # but hasn't pushed per-match times yet. Bounded to SCHEDULED + LIVE
    # so we don't drag in pre-historic Sackmann rows with missing dates.
    stmt_b = select(Match).where(
        base,
        Match.scheduled_at.is_(None),
        Match.status.in_([MatchStatus.SCHEDULED, MatchStatus.LIVE]),
    )
    if status_filter:
        from app.api._helpers import filter_status
        stmt_b = filter_status(stmt_b, status_filter)
    rows_undated = session.exec(stmt_b).all()

    # Within a tournament all matches share scheduled_at (Sackmann pins
    # it to the tournament start), so SQL tie-break is undefined. Re-sort
    # in Python by (sort_at, round_depth) descending so the deepest round
    # — the player's most recent match — sits at the top of each group.
    # For NULL-scheduled upcoming matches we substitute the tournament's
    # start_date, which puts those rows in the right week-bucket relative
    # to history with real timestamps.
    from datetime import date as _date, datetime as _dt, time as _time

    from app.models.tournament import Tournament
    from app.services.rounds import round_depth

    all_rows = list(rows_dated) + list(rows_undated)
    tournament_starts: dict[int, _date] = dict(
        session.exec(
            select(Tournament.id, Tournament.start_date)
            .where(Tournament.id.in_({m.tournament_id for m in all_rows if m.tournament_id}))
            .where(Tournament.start_date.is_not(None))
        ).all()
    )

    def _sort_at(m) -> _dt:
        if m.scheduled_at is not None:
            return m.scheduled_at
        ts = tournament_starts.get(m.tournament_id)
        if ts is not None:
            return _dt.combine(ts, _time.min)
        return _dt.min

    all_rows.sort(
        key=lambda m: (_sort_at(m), round_depth(m.round)),
        reverse=True,
    )
    return [match_to_summary(session, m) for m in all_rows[:limit]]


@router.get("/{slug}/snapshot", response_model=PlayerSnapshot)
def player_snapshot(slug: str, session: Session = Depends(get_session)) -> PlayerSnapshot:
    """Career snapshot: totals, titles, surface breakdown, biggest
    rival, recent form. Singles-only.

    One query gets the player's finished matches (with their
    tournaments + opponents joined as needed) and the rest is in-
    memory arithmetic. Cheap enough to compute on every page load —
    no caching needed yet.
    """
    p = session.exec(select(Player).where(Player.slug == slug)).first()
    if not p:
        raise HTTPException(404, "Player not found")

    # All finished singles matches involving the player. Sackmann
    # coverage means this is reasonably complete back to the 70s for
    # ATP / 80s for WTA — earlier seasons may be partial.
    matches = session.exec(
        select(Match)
        .where(
            or_(Match.player1_id == p.id, Match.player2_id == p.id),
            Match.status == MatchStatus.FINISHED,
            Match.is_doubles == False,  # noqa: E712 — SQLAlchemy expr
        )
        .order_by(Match.scheduled_at.desc())
    ).all()

    # Eager-load tournament metadata in one query.
    tournament_ids = {m.tournament_id for m in matches if m.tournament_id}
    tournaments: dict[int, Tournament] = {}
    if tournament_ids:
        for t in session.exec(
            select(Tournament).where(Tournament.id.in_(tournament_ids))
        ).all():
            tournaments[t.id] = t

    # Eager-load opponent names in one query — for the "biggest rival"
    # callout we need full names, not just slugs.
    opponent_ids: set[int] = set()
    for m in matches:
        if m.player1_id == p.id and m.player2_id:
            opponent_ids.add(m.player2_id)
        elif m.player2_id == p.id and m.player1_id:
            opponent_ids.add(m.player1_id)
    opponents: dict[int, Player] = {}
    if opponent_ids:
        for op in session.exec(
            select(Player).where(Player.id.in_(opponent_ids))
        ).all():
            opponents[op.id] = op

    # ---- Aggregate ----------------------------------------------------
    career_wins = career_losses = 0
    surface_wl: dict[str, list[int]] = defaultdict(lambda: [0, 0])  # [wins, losses]
    opponent_wl: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    titles: list[SnapshotTitle] = []
    finals_count = 0
    slam_titles = 0
    slam_finals = 0
    best_slam: SnapshotTitle | None = None

    recent_wins = recent_losses = 0
    RECENT_WINDOW = 20

    def _enum_or_str(v) -> str | None:
        """Tolerate both Enum and plain-string forms — SQLModel sometimes
        hydrates enums as their string value when the column is queried
        in isolation."""
        if v is None:
            return None
        return v.value if hasattr(v, "value") else str(v)

    for idx, m in enumerate(matches):
        t = tournaments.get(m.tournament_id)
        surface = _enum_or_str(t.surface) if t else None
        if not surface:
            surface = "unknown"
        is_p1 = m.player1_id == p.id
        opp_id = m.player2_id if is_p1 else m.player1_id

        # Win/loss attribution.
        if m.winner_id == p.id:
            career_wins += 1
            surface_wl[surface][0] += 1
            if opp_id is not None:
                opponent_wl[opp_id][0] += 1
            if idx < RECENT_WINDOW:
                recent_wins += 1
        elif m.winner_id is not None:
            career_losses += 1
            surface_wl[surface][1] += 1
            if opp_id is not None:
                opponent_wl[opp_id][1] += 1
            if idx < RECENT_WINDOW:
                recent_losses += 1

        # Final detection: round string ends with "final" (case-insensitive)
        # or equals "F". Both Wikipedia-shape ("F") and api-tennis-shape
        # ("... - Final") are caught.
        round_str = (m.round or "").lower().strip().rstrip("s")
        is_final = round_str.endswith("final") or round_str == "f"
        if is_final and t is not None and m.winner_id is not None:
            finals_count += 1
            opp = opponents.get(opp_id) if opp_id is not None else None
            cat = _enum_or_str(t.category)
            is_slam = cat == "grand_slam"
            if m.winner_id == p.id:
                title = SnapshotTitle(
                    year=t.year,
                    tournament_slug=t.slug,
                    tournament_name=t.name,
                    tournament_tour=_enum_or_str(t.tour) or "atp",
                    category=cat,
                    surface=surface if surface != "unknown" else None,
                    final_opponent_slug=opp.slug if opp else None,
                    final_opponent_name=opp.full_name if opp else None,
                    final_score=m.score,
                )
                titles.append(title)
                if is_slam:
                    slam_titles += 1
                    if best_slam is None or title.year > best_slam.year:
                        best_slam = title
            if is_slam:
                slam_finals += 1

    surfaces = [
        SurfaceRecord(surface=s, wins=v[0], losses=v[1])
        for s, v in sorted(surface_wl.items(), key=lambda kv: -(kv[1][0] + kv[1][1]))
        if s != "unknown"
    ]
    best_surface_pair = max(
        (s for s in surfaces),
        key=lambda s: s.wins,
        default=None,
    )

    # Biggest rival: opponent with the most meetings, tie-broken by the
    # one we've lost most to (more "real" rivalry signal than mowing
    # someone down). Then by name for determinism.
    biggest_rival_slug: str | None = None
    biggest_rival_name: str | None = None
    biggest_rival_wins = 0
    biggest_rival_losses = 0
    if opponent_wl:
        best_opp_id, (rw, rl) = max(
            opponent_wl.items(),
            key=lambda kv: (kv[1][0] + kv[1][1], kv[1][1], opponents.get(kv[0]).full_name if opponents.get(kv[0]) else ""),
        )
        op = opponents.get(best_opp_id)
        if op is not None and (rw + rl) >= 3:  # 3+ meetings to count as a rival
            biggest_rival_slug = op.slug
            biggest_rival_name = op.full_name
            biggest_rival_wins = rw
            biggest_rival_losses = rl

    # Recent titles, newest first.
    titles.sort(key=lambda x: (x.year, x.tournament_name), reverse=True)

    return PlayerSnapshot(
        slug=p.slug,
        full_name=p.full_name,
        career_wins=career_wins,
        career_losses=career_losses,
        career_titles=len(titles),
        career_finals=finals_count,
        slam_titles=slam_titles,
        slam_finals=slam_finals,
        best_slam=best_slam,
        recent_wins=recent_wins,
        recent_losses=recent_losses,
        surfaces=surfaces,
        best_surface=best_surface_pair.surface if best_surface_pair else None,
        biggest_rival_slug=biggest_rival_slug,
        biggest_rival_name=biggest_rival_name,
        biggest_rival_record_wins=biggest_rival_wins,
        biggest_rival_record_losses=biggest_rival_losses,
        recent_titles=titles[:5],
    )


@router.get("/{slug}/rankings")
def player_ranking_history(
    slug: str,
    limit: int = Query(260, ge=1, le=1040),  # 5 years of weeks default
    session: Session = Depends(get_session),
):
    p = session.exec(select(Player).where(Player.slug == slug)).first()
    if not p:
        raise HTTPException(404, "Player not found")
    rows = session.exec(
        select(Ranking).where(Ranking.player_id == p.id).order_by(Ranking.week.desc()).limit(limit)
    ).all()
    return [{"week": r.week, "rank": r.rank, "points": r.points} for r in rows]


@router.get("/{slug}/tournament-history", response_model=list[TournamentHistoryEntry])
def player_tournament_history(
    slug: str,
    limit: int = Query(5, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    """For each tournament the player has participated in, return how far
    they got: W (won the title), F (lost the final), SF, QF, R16, etc.
    Ordered by tournament date, most recent first.
    """
    p = session.exec(select(Player).where(Player.slug == slug)).first()
    if not p:
        raise HTTPException(404, "Player not found")

    rows = session.exec(
        select(Match, Tournament)
        .join(Tournament, Tournament.id == Match.tournament_id)
        .where(or_(Match.player1_id == p.id, Match.player2_id == p.id))
        .where(Match.status == MatchStatus.FINISHED)
    ).all()

    # Group matches by tournament instance (tournament rows are per-year, so
    # this naturally separates Wimbledon 2024 from Wimbledon 2025).
    by_tournament: dict[int, list[tuple[Match, Tournament]]] = defaultdict(list)
    for m, t in rows:
        by_tournament[t.id].append((m, t))

    entries: list[TournamentHistoryEntry] = []
    for _, group in by_tournament.items():
        t = group[0][1]
        deepest_match = max(group, key=lambda mt: round_depth(mt[0].round))[0]
        won_deepest = deepest_match.winner_id == p.id
        result = compute_player_result(deepest_match.round, won_deepest)
        entries.append(
            TournamentHistoryEntry(
                tournament_slug=t.slug,
                tournament_year=t.year,
                tournament_name=t.name,
                tournament_tour=t.tour.value,
                tournament_category=t.category.value if t.category else None,
                tournament_surface=t.surface,
                tournament_image_url=t.image_url,
                start_date=t.start_date,
                end_date=t.end_date,
                result=result,
                is_winner=result == "W",
            )
        )

    # Most recent first. Use end_date when present, else start_date, else year.
    def _sort_key(e: TournamentHistoryEntry) -> tuple[int, date]:
        d = e.end_date or e.start_date or date(e.tournament_year, 1, 1)
        return (e.tournament_year, d)

    entries.sort(key=_sort_key, reverse=True)
    return entries[offset : offset + limit]
