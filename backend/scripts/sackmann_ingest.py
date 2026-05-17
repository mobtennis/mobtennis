"""Ingest Jeff Sackmann's tennis_atp + tennis_wta CSVs into SQLite.

Sources (MIT licensed, free):
  https://github.com/JeffSackmann/tennis_atp
  https://github.com/JeffSackmann/tennis_wta

Run:
  uv run python -m scripts.sackmann_ingest
  uv run python -m scripts.sackmann_ingest --years 2023 2024 2025 2026
  uv run python -m scripts.sackmann_ingest --tour atp

The script is idempotent — re-running upserts.
"""

import argparse
import csv
import io
import logging
from datetime import date, datetime
from pathlib import Path

import httpx
from slugify import slugify
from sqlmodel import Session, select

from app.db.session import engine, init_db
from app.models.match import Match, MatchStatus
from app.models.player import Player, Tour
from app.models.ranking import Ranking
from app.models.tournament import Tournament, TournamentCategory

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("sackmann")

ATP_BASE = "https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master"
WTA_BASE = "https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master"

DATA_RAW = Path(__file__).resolve().parents[2] / "data" / "raw"
DATA_RAW.mkdir(parents=True, exist_ok=True)


def _fetch(url: str) -> str:
    cached = DATA_RAW / Path(url).name
    if cached.exists():
        return cached.read_text(encoding="utf-8", errors="ignore")
    log.info("fetching %s", url)
    r = httpx.get(url, timeout=60, follow_redirects=True)
    r.raise_for_status()
    cached.write_text(r.text, encoding="utf-8", errors="ignore")
    return r.text


def _parse_date(s: str | None) -> date | None:
    if not s or len(s) < 8:
        return None
    try:
        return datetime.strptime(s, "%Y%m%d").date()
    except ValueError:
        return None


def _category_from_level(level: str | None) -> TournamentCategory:
    m = {
        "G": TournamentCategory.GRAND_SLAM,
        "M": TournamentCategory.ATP_1000,
        "A": TournamentCategory.ATP_500,
        "B": TournamentCategory.ATP_250,
        "F": TournamentCategory.ATP_FINALS,
        "D": TournamentCategory.DAVIS_CUP,
        "P": TournamentCategory.WTA_1000,
        "PM": TournamentCategory.WTA_1000,
        "I": TournamentCategory.WTA_500,
        "T1": TournamentCategory.WTA_500,
        "C": TournamentCategory.CHALLENGER,
    }
    return m.get((level or "").upper(), TournamentCategory.OTHER)


def ingest_players(session: Session, tour: Tour) -> int:
    """Ingest Sackmann player metadata.

    Reconciliation order — first match wins, so historical match data attaches
    to existing rows instead of creating a parallel "Sinner" with a suffixed
    slug:
      1. Already-tagged with this sackmann_id → reuse
      2. Same (full_name, tour) → attach sackmann_id to that row
      3. Same slug → attach sackmann_id (the api-tennis ingest creates rows
         with the slugified full name, so this catches most matches)
      4. Otherwise: create a new row, suffix the slug if needed to avoid
         a unique-slug clash.
    """
    base = ATP_BASE if tour == Tour.ATP else WTA_BASE
    fname = "atp_players.csv" if tour == Tour.ATP else "wta_players.csv"
    text = _fetch(f"{base}/{fname}")

    count_added = 0
    count_attached = 0
    for row in csv.DictReader(io.StringIO(text)):
        pid = row.get("player_id")
        if not pid:
            continue
        first = (row.get("name_first") or "").strip()
        last = (row.get("name_last") or "").strip()
        full = f"{first} {last}".strip() or row.get("name") or ""
        if not full:
            continue
        slug = slugify(full)[:80]

        dob = _parse_date(row.get("dob"))
        height = row.get("height")
        height_cm = int(height) if height and height.isdigit() else None
        country = (row.get("ioc") or "").upper() or None

        # 1. Already linked
        existing = session.exec(
            select(Player).where(Player.sackmann_id == pid, Player.tour == tour)
        ).first()
        if existing:
            continue

        # 2. Same name + tour (most reliable cross-source match for active pros)
        existing = session.exec(
            select(Player).where(Player.full_name == full, Player.tour == tour)
        ).first()
        # 3. Same slug + tour (fallback)
        if not existing:
            existing = session.exec(
                select(Player).where(Player.slug == slug, Player.tour == tour)
            ).first()

        if existing:
            existing.sackmann_id = pid
            if dob and not existing.birth_date:
                existing.birth_date = dob
            if height_cm and not existing.height_cm:
                existing.height_cm = height_cm
            if country and not existing.country_code:
                existing.country_code = country
            if first and not existing.first_name:
                existing.first_name = first
            if last and not existing.last_name:
                existing.last_name = last
            session.add(existing)
            count_attached += 1
        else:
            # Net-new player — disambiguate slug if a different-tour player
            # already owns it.
            clash = session.exec(select(Player).where(Player.slug == slug)).first()
            if clash:
                slug = f"{slug}-{pid}"
            session.add(
                Player(
                    slug=slug,
                    full_name=full,
                    first_name=first or None,
                    last_name=last or None,
                    tour=tour,
                    country_code=country,
                    birth_date=dob,
                    height_cm=height_cm,
                    plays=row.get("hand"),
                    sackmann_id=pid,
                )
            )
            count_added += 1

        if (count_added + count_attached) % 2000 == 0:
            session.commit()
            log.info("  %d %s players...", count_added + count_attached, tour.value)
    session.commit()
    log.info(
        "ingested %d %s players (%d new + %d attached)",
        count_added + count_attached, tour.value, count_added, count_attached,
    )
    return count_added + count_attached


def ingest_matches(session: Session, tour: Tour, years: list[int]) -> int:
    base = ATP_BASE if tour == Tour.ATP else WTA_BASE
    prefix = "atp_matches" if tour == Tour.ATP else "wta_matches"

    # Cache player lookups for the whole run
    pid_map: dict[str, int] = {
        sid: pk
        for sid, pk in session.exec(
            select(Player.sackmann_id, Player.id).where(Player.tour == tour, Player.sackmann_id != None)  # noqa: E711
        ).all()
    }

    total = 0
    for year in years:
        url = f"{base}/{prefix}_{year}.csv"
        try:
            text = _fetch(url)
        except httpx.HTTPStatusError:
            log.warning("no %s data for %s", tour.value, year)
            continue

        # Common slug aliases — Sackmann names sometimes differ from api-tennis.
        # Map the Sackmann form → our canonical slug so historical rows attach
        # to existing live rows instead of creating parallel entries.
        slug_aliases = {
            "roland-garros": "french-open",
            "the-championships": "wimbledon",
            "wimbledon-championships": "wimbledon",
            "italian-open": "rome",
            "internazionali-bnl-d-italia": "rome",
        }

        tournaments_seen: dict[str, Tournament] = {}
        year_count = 0
        for row in csv.DictReader(io.StringIO(text)):
            tname = row.get("tourney_name") or "Unknown"
            tslug = slug_aliases.get(slugify(tname)[:80], slugify(tname)[:80])
            tkey = f"{tslug}-{year}"
            if tkey in tournaments_seen:
                tournament = tournaments_seen[tkey]
            else:
                tournament = session.exec(
                    select(Tournament).where(
                        Tournament.slug == tslug,
                        Tournament.year == year,
                        Tournament.tour == tour,
                    )
                ).first()
                if tournament:
                    # Attach the sackmann_id and backfill blanks; leave the
                    # tournament's name/category alone (live data is canonical).
                    if not tournament.sackmann_id:
                        tournament.sackmann_id = row.get("tourney_id")
                    if not tournament.surface:
                        tournament.surface = (row.get("surface") or "").lower() or None
                    if not tournament.start_date:
                        tournament.start_date = _parse_date(row.get("tourney_date"))
                    if not tournament.draw_size and (row.get("draw_size") or "").isdigit():
                        tournament.draw_size = int(row.get("draw_size"))
                    session.add(tournament)
                else:
                    tournament = Tournament(
                        slug=tslug,
                        year=year,
                        name=tname,
                        tour=tour,
                        category=_category_from_level(row.get("tourney_level")),
                        surface=(row.get("surface") or "").lower() or None,
                        start_date=_parse_date(row.get("tourney_date")),
                        draw_size=int(row.get("draw_size")) if (row.get("draw_size") or "").isdigit() else None,
                        sackmann_id=row.get("tourney_id"),
                    )
                    session.add(tournament)
                    session.flush()
                tournaments_seen[tkey] = tournament

            w_id = pid_map.get(row.get("winner_id"))
            l_id = pid_map.get(row.get("loser_id"))
            if not w_id or not l_id:
                continue

            sackmann_match_id = f"{row.get('tourney_id')}-{row.get('match_num')}"
            # Sackmann uses identical (tourney_id, match_num) keys for ATP and
            # WTA versions of joint slams (Wimbledon ATP and WTA both have
            # match #100..226). Scope dedup by tour or the WTA pass silently
            # skips half the slams.
            existing = session.exec(
                select(Match)
                .join(Tournament, Tournament.id == Match.tournament_id)
                .where(Match.sackmann_id == sackmann_match_id, Tournament.tour == tour)
            ).first()
            if existing:
                continue

            best_of_raw = row.get("best_of")
            best_of = int(best_of_raw) if best_of_raw and best_of_raw.isdigit() else 3

            session.add(
                Match(
                    tournament_id=tournament.id,
                    round=row.get("round"),
                    scheduled_at=datetime.combine(
                        _parse_date(row.get("tourney_date")) or date(year, 1, 1),
                        datetime.min.time(),
                    ),
                    finished_at=datetime.combine(
                        _parse_date(row.get("tourney_date")) or date(year, 1, 1),
                        datetime.min.time(),
                    ),
                    status=MatchStatus.FINISHED,
                    player1_id=w_id,
                    player2_id=l_id,
                    score=row.get("score"),
                    winner_id=w_id,
                    is_doubles=False,
                    best_of=best_of,
                    sackmann_id=sackmann_match_id,
                )
            )
            year_count += 1
            if year_count % 1000 == 0:
                session.commit()
        session.commit()
        log.info("  %s %d: %d matches", tour.value, year, year_count)
        total += year_count
    return total


def ingest_rankings_current(session: Session, tour: Tour) -> int:
    """Ingest the latest rankings file. Sackmann publishes per-decade & current."""
    base = ATP_BASE if tour == Tour.ATP else WTA_BASE
    fname = "atp_rankings_current.csv" if tour == Tour.ATP else "wta_rankings_current.csv"
    text = _fetch(f"{base}/{fname}")

    pid_map: dict[str, int] = {
        sid: pk
        for sid, pk in session.exec(
            select(Player.sackmann_id, Player.id).where(Player.tour == tour, Player.sackmann_id != None)  # noqa: E711
        ).all()
    }

    count = 0
    latest_week: date | None = None
    for row in csv.DictReader(io.StringIO(text)):
        week = _parse_date(row.get("ranking_date"))
        if not week:
            continue
        latest_week = max(latest_week, week) if latest_week else week
        pid = pid_map.get(row.get("player"))
        if not pid:
            continue
        rank_raw = row.get("rank")
        if not rank_raw or not rank_raw.isdigit():
            continue
        points = row.get("points")
        existing = session.exec(
            select(Ranking).where(
                Ranking.player_id == pid, Ranking.tour == tour, Ranking.week == week
            )
        ).first()
        if existing:
            continue
        session.add(
            Ranking(
                player_id=pid,
                tour=tour,
                week=week,
                rank=int(rank_raw),
                points=int(points) if points and points.isdigit() else None,
            )
        )
        count += 1

    session.commit()

    # Update Player.current_rank from latest week.
    if latest_week:
        latest_rows = session.exec(
            select(Ranking).where(Ranking.tour == tour, Ranking.week == latest_week)
        ).all()
        for r in latest_rows:
            p = session.get(Player, r.player_id)
            if p and (p.current_rank is None or r.rank < (p.career_high_rank or 1_000_000)):
                if p.current_rank is None or True:
                    p.current_rank = r.rank
                if p.career_high_rank is None or r.rank < p.career_high_rank:
                    p.career_high_rank = r.rank
                session.add(p)
        session.commit()

    log.info("ingested %d %s ranking rows (latest week %s)", count, tour.value, latest_week)
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tour", choices=["atp", "wta", "both"], default="both")
    parser.add_argument(
        "--years", type=int, nargs="+", default=list(range(2020, date.today().year + 1))
    )
    parser.add_argument("--skip-matches", action="store_true")
    args = parser.parse_args()

    init_db()
    tours: list[Tour] = (
        [Tour.ATP, Tour.WTA] if args.tour == "both"
        else [Tour.ATP] if args.tour == "atp" else [Tour.WTA]
    )

    with Session(engine) as session:
        for tour in tours:
            log.info("=== %s ===", tour.value.upper())
            ingest_players(session, tour)
            if not args.skip_matches:
                ingest_matches(session, tour, args.years)
            ingest_rankings_current(session, tour)


if __name__ == "__main__":
    main()
