"""Backfill Match.duration_minutes from the local Sackmann CSVs.

The main ingest now stores `minutes` for new rows, but existing history was
imported before the column existed. This reads data/raw/{atp,wta}_matches_*.csv
(the same local cache the ingest uses — Sackmann's GitHub is gone, but the
files are still on disk) and sets duration_minutes on matching Match rows,
keyed by sackmann_id = "{tourney_id}-{match_num}", scoped by tour.

Idempotent. Usage:
    python -m scripts.minutes_backfill                 # all years present
    python -m scripts.minutes_backfill --years 2024 2025
"""

from __future__ import annotations

import argparse
import csv
import io

from sqlmodel import Session, select

from app.db.session import engine, init_db
from app.models.match import Match
from app.models.player import Tour
from app.models.tournament import Tournament
from scripts.sackmann_ingest import DATA_RAW

_PREFIX = {Tour.ATP: "atp_matches", Tour.WTA: "wta_matches"}


def backfill(years: list[int]) -> None:
    init_db()
    total_set = 0
    total_seen = 0
    with Session(engine) as session:
        for tour in (Tour.ATP, Tour.WTA):
            # Map sackmann_id -> Match.id for this tour (one query per tour).
            id_map: dict[str, int] = {
                sid: mid
                for sid, mid in session.exec(
                    select(Match.sackmann_id, Match.id)
                    .join(Tournament, Tournament.id == Match.tournament_id)
                    .where(Match.sackmann_id.is_not(None), Tournament.tour == tour)
                ).all()
            }
            for year in years:
                path = DATA_RAW / f"{_PREFIX[tour]}_{year}.csv"
                if not path.exists():
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
                pending: list[tuple[int, int]] = []  # (match_id, minutes)
                for row in csv.DictReader(io.StringIO(text)):
                    mins = (row.get("minutes") or "").strip()
                    if not mins.isdigit():
                        continue
                    total_seen += 1
                    sid = f"{row.get('tourney_id')}-{row.get('match_num')}"
                    mid = id_map.get(sid)
                    if mid is not None:
                        pending.append((mid, int(mins)))
                # Apply in bulk per (tour, year).
                for mid, mins in pending:
                    m = session.get(Match, mid)
                    if m and m.duration_minutes != mins:
                        m.duration_minutes = mins
                        session.add(m)
                        total_set += 1
                session.commit()
                if pending:
                    print(f"  {tour.value} {year}: matched {len(pending)} rows")
    print(f"done — set duration on {total_set} matches (saw {total_seen} rows with minutes)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, nargs="*", default=list(range(2017, 2027)))
    args = ap.parse_args()
    backfill(args.years)
