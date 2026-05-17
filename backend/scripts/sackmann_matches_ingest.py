"""Ingest Sackmann historical match data.

Downloads the per-year matches CSV from Jeff Sackmann's tennis_atp /
tennis_wta GitHub repositories and upserts Tournament + Match rows.
Sackmann is the authoritative source for completed tournaments
(scores, seeds, surface, draw_size) — we use it to fill gaps that
api-tennis missed (we only poll today + listen to live, so anything
that played while the box was off / before we started never lands).

Idempotency: each match gets `sackmann_id = "{tourney_id}-{match_num}"`.
Re-runs skip already-imported matches. When api-tennis already has a
fixture (matched by tournament + player pair + round), we attach the
sackmann_id and backfill missing fields — never overwriting live data.

Safe under load: commits in small chunks (COMMIT_EVERY) so the SQLite
writer lock isn't held for the full ingest. Designed to be runnable
on a live prod box without taking the API down.

Usage on the box:
  sudo -u tennismob /opt/tennismob/backend/.venv/bin/python \\
    /opt/tennismob/backend/scripts/sackmann_matches_ingest.py \\
    --tour atp --year 2026

Both tours, multiple years:
  for tour in atp wta; do
    for year in 2024 2025 2026; do
      sudo -u tennismob /opt/tennismob/backend/.venv/bin/python \\
        /opt/tennismob/backend/scripts/sackmann_matches_ingest.py \\
        --tour $tour --year $year
    done
  done

License: Sackmann's data is CC BY-NC-SA 4.0. Attribution is handled
on the /credits page.
"""

from __future__ import annotations

import argparse
import csv
import io
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path


def _load_env_file() -> None:
    env_file = Path(__file__).resolve().parents[1] / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env_file()

import httpx  # noqa: E402
from slugify import slugify  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

from app.db.session import engine  # noqa: E402
from app.models.match import Match, MatchStatus  # noqa: E402
from app.models.player import Player, Tour  # noqa: E402
from app.models.tournament import Tournament  # noqa: E402
from app.services.categorize import categorize  # noqa: E402
from app.services.player_dedup import find_player_by_name, name_key  # noqa: E402


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("sackmann_matches_ingest")


_BASE_URLS: dict[Tour, str] = {
    Tour.ATP: "https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_matches_{year}.csv",
    Tour.WTA: "https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_matches_{year}.csv",
}

# Sackmann uses official "long" tournament names ("Monte Carlo Masters",
# "Italian Open", "Mutua Madrid Open") while api-tennis ships shorter
# venue names ("Monte Carlo", "Rome", "Madrid"). The two slugify to
# different keys, so without this alias map we end up with parallel
# rows for the same brand. Manually curated for top-tier events — for
# Challengers / ITF the names tend to agree between sources, so no
# alias is needed.
#
# Map values are the canonical slug already used by api-tennis (i.e.
# whichever string we'd pass to /tournaments/<tour>/<slug>/<year>).
_SACKMANN_NAME_TO_SLUG: dict[str, str] = {
    # Grand Slams
    "Australian Open":              "australian-open",
    "Roland Garros":                "roland-garros",
    "Roland-Garros":                "roland-garros",
    "French Open":                  "roland-garros",
    "Wimbledon":                    "wimbledon",
    "The Championships, Wimbledon": "wimbledon",
    "US Open":                      "us-open",
    "Us Open":                      "us-open",
    # ATP / WTA 1000
    "Indian Wells Masters":         "indian-wells",
    "BNP Paribas Open":             "indian-wells",
    "Miami Masters":                "miami",
    "Miami Open":                   "miami",
    "Monte Carlo Masters":          "monte-carlo",
    "Madrid Masters":               "madrid",
    "Mutua Madrid Open":            "madrid",
    "Italian Open":                 "rome",
    "Rome Masters":                 "rome",
    "Internazionali BNL d'Italia":  "rome",
    "Canadian Open":                "canada",
    "Canada Masters":               "canada",
    "Cincinnati Masters":           "cincinnati",
    "Western & Southern Open":      "cincinnati",
    "Shanghai Masters":             "shanghai",
    "Rolex Shanghai Masters":       "shanghai",
    "Paris Masters":                "paris",
    "Rolex Paris Masters":          "paris",
    "Dubai Tennis Championships":   "dubai",
    "Qatar Open":                   "doha",
    # ATP / WTA Finals
    "Tour Finals":                  "atp-finals",
    "Nitto ATP Finals":             "atp-finals",
    "WTA Finals":                   "wta-finals",
    "WTA Tour Championships":       "wta-finals",
}


def _canonical_slug(sackmann_name: str) -> str:
    """Map a Sackmann tournament name to the canonical slug api-tennis
    would have used. Falls back to standard slugification when not
    in the alias table."""
    if sackmann_name in _SACKMANN_NAME_TO_SLUG:
        return _SACKMANN_NAME_TO_SLUG[sackmann_name]
    return slugify(sackmann_name)[:80]

# Map Sackmann round labels onto our internal canonical names. Sackmann
# uses the same letters we do for the standard rounds; the exotic ones
# (Bronze, Round Robin) we tag clearly so they don't pretend to be a
# main-draw round.
_ROUND_MAP: dict[str, str] = {
    "F": "F",
    "SF": "SF",
    "QF": "QF",
    "R16": "R16",
    "R32": "R32",
    "R64": "R64",
    "R128": "R128",
    "BR": "Bronze",
    "RR": "Round Robin",
}

# How often we session.commit() during the ingest. SQLite under WAL is
# happy with many connections but ONE writer at a time; flushing every
# few dozen rows keeps the writer lock available for live ingest
# (api-tennis WS + scheduled jobs) instead of holding it for the
# entire 1500-row file.
_COMMIT_EVERY = 50


def _download_csv(tour: Tour, year: int) -> str:
    url = _BASE_URLS[tour].format(year=year)
    log.info("fetching %s", url)
    r = httpx.get(url, timeout=30.0, follow_redirects=True)
    r.raise_for_status()
    return r.text


def _norm_surface(s: str | None) -> str | None:
    if not s:
        return None
    s = s.strip().lower()
    return s if s in ("hard", "clay", "grass", "carpet") else None


def _parse_yyyymmdd(s: str | None) -> date | None:
    if not s:
        return None
    s = s.strip()
    if len(s) == 8 and s.isdigit():
        try:
            return date(int(s[0:4]), int(s[4:6]), int(s[6:8]))
        except ValueError:
            return None
    return None


def _int_or_none(s: str | None) -> int | None:
    if not s:
        return None
    s = s.strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def _find_or_create_tournament(
    session: Session,
    *,
    name: str,
    tour: Tour,
    year: int,
    surface: str | None,
    draw_size: int | None,
    tourney_date: date | None,
) -> Tournament:
    # Resolve to the canonical slug api-tennis would use, so we attach
    # Sackmann matches to the existing tournament row rather than
    # creating a parallel "monte-carlo-masters" row alongside the
    # api-tennis "monte-carlo" one.
    slug = _canonical_slug(name)
    stmt = select(Tournament).where(
        Tournament.slug == slug,
        Tournament.year == year,
        Tournament.tour == tour,
    )
    t = session.exec(stmt).first()
    if t:
        # Backfill missing fields only — never overwrite values that
        # api-tennis or Wikipedia already supplied.
        changed = False
        if surface and not t.surface:
            t.surface = surface
            changed = True
        if draw_size and not t.draw_size:
            t.draw_size = draw_size
            changed = True
        if tourney_date and not t.start_date:
            t.start_date = tourney_date
            changed = True
        if changed:
            session.add(t)
        return t
    t = Tournament(
        slug=slug,
        year=year,
        name=name,
        tour=tour,
        category=categorize(name, tour),
        surface=surface,
        draw_size=draw_size,
        start_date=tourney_date,
    )
    session.add(t)
    session.flush()
    return t


def _find_or_create_player(
    session: Session,
    *,
    name: str,
    tour: Tour,
    ioc: str | None,
    sackmann_pid: str | None,
) -> Player:
    if sackmann_pid:
        existing = session.exec(
            select(Player).where(Player.sackmann_id == sackmann_pid)
        ).first()
        if existing:
            if existing.name_key is None:
                existing.name_key = name_key(existing.full_name)
                session.add(existing)
            return existing

    by_name = find_player_by_name(session, name, tour)
    if by_name:
        if sackmann_pid and not by_name.sackmann_id:
            by_name.sackmann_id = sackmann_pid
            session.add(by_name)
        if ioc and not by_name.country_code:
            by_name.country_code = ioc
            session.add(by_name)
        return by_name

    base_slug = slugify(name)[:80] or f"player-{sackmann_pid or 'x'}"
    existing_slug = session.exec(
        select(Player).where(Player.slug == base_slug)
    ).first()
    if existing_slug is None:
        slug = base_slug
    else:
        # Slug collides across tours / different players. Suffix to make unique.
        suffix = sackmann_pid or tour.value
        slug = f"{base_slug}-{suffix}"
        if session.exec(select(Player).where(Player.slug == slug)).first():
            slug = f"{base_slug}-{tour.value}-{sackmann_pid or 'x'}"

    p = Player(
        slug=slug,
        full_name=name,
        tour=tour,
        country_code=ioc or None,
        sackmann_id=sackmann_pid,
        name_key=name_key(name),
    )
    session.add(p)
    session.flush()
    return p


def _find_existing_match(
    session: Session,
    *,
    tournament_id: int,
    p1_id: int,
    p2_id: int,
    round_label: str,
) -> Match | None:
    """Find a Match in the same tournament + round containing this
    player pair (order-insensitive). Used to detect rows api-tennis
    already inserted so Sackmann doesn't double-write."""
    stmt = select(Match).where(
        Match.tournament_id == tournament_id,
        Match.is_doubles == False,  # noqa: E712 — we ingest only singles here
    )
    candidates = session.exec(stmt).all()
    target = {p1_id, p2_id}
    for m in candidates:
        if not m.round:
            continue
        # Round label match — Sackmann labels are exact, api-tennis uses
        # e.g. "ATP Rome - Quarter-finals" so substring-match the canonical.
        if round_label.lower() not in (m.round or "").lower():
            # Also try the api-tennis "1/N-finals" form for early rounds.
            fragments = {
                "R16": "1/8-final",
                "R32": "1/16-final",
                "R64": "1/32-final",
                "R128": "1/64-final",
            }
            frag = fragments.get(round_label, "")
            if not (frag and frag in (m.round or "").lower()):
                continue
        pair = {m.player1_id, m.player2_id}
        if pair == target:
            return m
    return None


def _ingest_row(session: Session, row: dict, tour: Tour) -> tuple[int, int, int]:
    """Process one CSV row. Returns (added, updated, skipped)."""
    tourney_id = (row.get("tourney_id") or "").strip()
    match_num = (row.get("match_num") or "").strip()
    if not tourney_id or not match_num:
        return 0, 0, 1
    sackmann_id = f"{tourney_id}-{match_num}"

    # Already imported by us? Skip outright.
    if session.exec(
        select(Match).where(Match.sackmann_id == sackmann_id)
    ).first():
        return 0, 0, 1

    tourney_name = (row.get("tourney_name") or "").strip()
    if not tourney_name:
        return 0, 0, 1

    winner_name = (row.get("winner_name") or "").strip()
    loser_name = (row.get("loser_name") or "").strip()
    if not winner_name or not loser_name:
        return 0, 0, 1

    surface = _norm_surface(row.get("surface"))
    draw_size = _int_or_none(row.get("draw_size"))
    tourney_date = _parse_yyyymmdd(row.get("tourney_date"))
    year = tourney_date.year if tourney_date else datetime.utcnow().year

    tournament = _find_or_create_tournament(
        session,
        name=tourney_name,
        tour=tour,
        year=year,
        surface=surface,
        draw_size=draw_size,
        tourney_date=tourney_date,
    )
    if tournament.id is None:
        return 0, 0, 1

    winner = _find_or_create_player(
        session,
        name=winner_name,
        tour=tour,
        ioc=(row.get("winner_ioc") or "").strip() or None,
        sackmann_pid=(row.get("winner_id") or "").strip() or None,
    )
    loser = _find_or_create_player(
        session,
        name=loser_name,
        tour=tour,
        ioc=(row.get("loser_ioc") or "").strip() or None,
        sackmann_pid=(row.get("loser_id") or "").strip() or None,
    )
    if winner.id is None or loser.id is None:
        return 0, 0, 1

    round_raw = (row.get("round") or "").strip().upper()
    round_label = _ROUND_MAP.get(round_raw, round_raw)
    score = (row.get("score") or "").strip() or None
    best_of = _int_or_none(row.get("best_of")) or 3
    winner_seed = _int_or_none(row.get("winner_seed"))
    loser_seed = _int_or_none(row.get("loser_seed"))

    finished_at = datetime.combine(tourney_date, datetime.min.time()) if tourney_date else None

    existing = _find_existing_match(
        session,
        tournament_id=tournament.id,
        p1_id=winner.id,
        p2_id=loser.id,
        round_label=round_label,
    )
    if existing:
        # Attach Sackmann id; backfill missing fields. Don't clobber
        # any live-supplied values — the only fields we touch are those
        # we know upstream didn't set.
        if not existing.sackmann_id:
            existing.sackmann_id = sackmann_id
        if existing.status not in (MatchStatus.FINISHED, MatchStatus.RETIRED, MatchStatus.WALKOVER):
            existing.status = MatchStatus.FINISHED
        if not existing.score:
            existing.score = score
        if not existing.winner_id:
            existing.winner_id = winner.id
        if not existing.finished_at and finished_at:
            existing.finished_at = finished_at
        # Seeds: assign per slot. api-tennis stores arbitrary
        # player1/player2 assignment; map Sackmann's winner/loser seeds
        # onto the right slot.
        if existing.player1_id == winner.id:
            if existing.player1_seed is None:
                existing.player1_seed = winner_seed
            if existing.player2_seed is None:
                existing.player2_seed = loser_seed
        elif existing.player1_id == loser.id:
            if existing.player1_seed is None:
                existing.player1_seed = loser_seed
            if existing.player2_seed is None:
                existing.player2_seed = winner_seed
        session.add(existing)
        return 0, 1, 0

    # Fresh insert. Sackmann's row is winner-first; we store winner as
    # player1 by convention (api-tennis arbitrary; for Sackmann-only
    # rows this gives a deterministic ordering).
    m = Match(
        tournament_id=tournament.id,
        round=round_label,
        scheduled_at=finished_at,
        finished_at=finished_at,
        status=MatchStatus.FINISHED,
        player1_id=winner.id,
        player2_id=loser.id,
        score=score,
        winner_id=winner.id,
        is_doubles=False,
        best_of=best_of,
        sackmann_id=sackmann_id,
        player1_seed=winner_seed,
        player2_seed=loser_seed,
    )
    session.add(m)
    return 1, 0, 0


def ingest(tour: Tour, year: int, limit: int | None = None) -> dict:
    """End-to-end ingest. Returns counts."""
    csv_text = _download_csv(tour, year)
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    log.info("parsed %d rows from %s %d", len(rows), tour.value, year)
    if limit:
        rows = rows[:limit]

    added = updated = skipped = errors = 0
    with Session(engine) as session:
        for i, row in enumerate(rows):
            try:
                a, u, s = _ingest_row(session, row, tour)
                added += a
                updated += u
                skipped += s
            except Exception:
                log.exception("row %d (%s) failed", i, row.get("tourney_name"))
                errors += 1
                # Roll back the failed row so we don't poison the session.
                session.rollback()
                continue
            if (i + 1) % _COMMIT_EVERY == 0:
                session.commit()
                log.info(
                    "progress: %d/%d (added=%d updated=%d skipped=%d errors=%d)",
                    i + 1, len(rows), added, updated, skipped, errors,
                )
        session.commit()

        # Post-step: reconstruct bracket_position for every tournament we
        # just touched, from the winner tree. Sackmann's match_num isn't
        # draw-position-aware, so without this past-tournament brackets
        # render with seeded players clumped at the top of every round.
        from app.services.bracket_reconstruct import reconstruct_from_winner_tree
        from sqlalchemy import text as _text
        touched_ids = list(session.exec(_text(
            "SELECT DISTINCT t.id FROM tournaments t "
            "JOIN matches m ON m.tournament_id = t.id "
            "WHERE m.sackmann_id IS NOT NULL AND t.tour = :tour AND t.year = :year"
        ).bindparams(tour=tour.value.upper(), year=year)).all())
        reconstructed = 0
        for (tid,) in touched_ids:
            r = reconstruct_from_winner_tree(session, tid)
            if r["placed"] > 0:
                reconstructed += 1
        if reconstructed:
            session.commit()
            log.info("bracket reconstruction: %d tournament(s)", reconstructed)
    return {"added": added, "updated": updated, "skipped": skipped, "errors": errors, "total": len(rows)}


def consolidate_duplicates(apply: bool = False) -> dict:
    """Normalise tournament slugs to the api-tennis canonical form.

    Walks `_SACKMANN_NAME_TO_SLUG`. For each `(source_name → target_slug)`
    entry, finds Tournament rows currently sitting at the source slug
    (e.g. an old Sackmann ingest left them as "monte-carlo-masters" or
    "french-open") and either:

      - **merges** them into the existing canonical row at target_slug
        for the same (year, tour), moving Match rows and deleting the
        source; or

      - **renames** the source row's slug to target_slug when no
        canonical row exists yet for that (year, tour).

    Dry-run by default. Pass `apply=True` to commit.
    """
    moved_matches = 0
    deleted_tournaments = 0
    renamed_tournaments = 0
    merges: list[tuple[Tournament, Tournament]] = []
    renames: list[Tournament] = []

    with Session(engine) as session:
        for sackmann_name, target_slug in _SACKMANN_NAME_TO_SLUG.items():
            source_slug = slugify(sackmann_name)[:80]
            if source_slug == target_slug:
                continue
            source_rows = session.exec(
                select(Tournament).where(Tournament.slug == source_slug)
            ).all()
            for source in source_rows:
                target = session.exec(
                    select(Tournament).where(
                        Tournament.slug == target_slug,
                        Tournament.year == source.year,
                        Tournament.tour == source.tour,
                    )
                ).first()
                if target is not None and target.id != source.id:
                    merges.append((source, target))
                elif target is None:
                    renames.append(source)

        log.info(
            "consolidation %s: %d merge pair(s), %d rename(s)",
            "apply" if apply else "dry-run", len(merges), len(renames),
        )

        for source, target in merges:
            matches = session.exec(
                select(Match).where(Match.tournament_id == source.id)
            ).all()
            log.info(
                "  merge %s/%d/%s [%d matches] → %s [%d existing]",
                source.slug, source.year, source.tour.value, len(matches),
                target.slug, len(session.exec(
                    select(Match).where(Match.tournament_id == target.id)
                ).all()),
            )
            if not apply:
                moved_matches += len(matches)
                continue
            for m in matches:
                m.tournament_id = target.id
                session.add(m)
                moved_matches += 1
            if not target.surface and source.surface:
                target.surface = source.surface
            if not target.draw_size and source.draw_size:
                target.draw_size = source.draw_size
            if not target.start_date and source.start_date:
                target.start_date = source.start_date
            session.add(target)
            session.delete(source)
            deleted_tournaments += 1

        for source in renames:
            new_slug = _SACKMANN_NAME_TO_SLUG[
                # source.name might not be in the map directly; we know
                # source.slug == slugify(some_alias_key), so just look up
                # by iterating. Cheap because the map is small.
                next(k for k, v in _SACKMANN_NAME_TO_SLUG.items()
                     if slugify(k)[:80] == source.slug)
            ]
            log.info(
                "  rename %s/%d/%s → %s/%d/%s",
                source.slug, source.year, source.tour.value,
                new_slug, source.year, source.tour.value,
            )
            if not apply:
                continue
            source.slug = new_slug
            session.add(source)
            renamed_tournaments += 1

        if apply:
            session.commit()

    return {
        "merges": len(merges),
        "renames": len(renames),
        "moved_matches": moved_matches,
        "deleted_tournaments": deleted_tournaments,
        "renamed_tournaments": renamed_tournaments,
        "applied": apply,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd")

    ing = sub.add_parser("ingest", help="ingest a Sackmann year file (default)")
    ing.add_argument("--tour", required=True, choices=["atp", "wta"])
    ing.add_argument("--year", type=int, required=True)
    ing.add_argument("--limit", type=int, default=None, help="cap rows for testing")

    cons = sub.add_parser("consolidate", help="merge duplicate Tournament rows")
    cons.add_argument("--apply", action="store_true",
                      help="actually commit; without this we just dry-run")

    # Back-compat: if no sub-command, default to `ingest` with original
    # positional flags so existing invocations keep working.
    ap.add_argument("--tour", choices=["atp", "wta"])
    ap.add_argument("--year", type=int)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    if args.cmd == "consolidate":
        result = consolidate_duplicates(apply=args.apply)
        log.info("consolidate done: %s", result)
        return 0

    # Treat absent sub-command + bare --tour/--year as `ingest`.
    cmd_tour = getattr(args, "tour", None)
    cmd_year = getattr(args, "year", None)
    cmd_limit = getattr(args, "limit", None)
    if cmd_tour is None or cmd_year is None:
        ap.print_help()
        return 1
    if cmd_year < 2000 or cmd_year > datetime.utcnow().year + 1:
        log.error("year out of plausible range: %d", cmd_year)
        return 1

    tour = Tour(cmd_tour)
    result = ingest(tour, cmd_year, cmd_limit)
    log.info(
        "done: total=%d added=%d updated=%d skipped=%d errors=%d",
        result["total"], result["added"], result["updated"], result["skipped"], result["errors"],
    )
    return 0 if result["errors"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
