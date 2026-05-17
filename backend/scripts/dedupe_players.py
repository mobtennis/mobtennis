"""Merge duplicate Player rows by name_key + tour.

Same human, different name spellings across sources, end up as separate
Player rows. This finds them via the order-insensitive `name_key` column
and merges every group into one canonical row, repointing all foreign
keys (matches, rankings, server slot) to the survivor.

Idempotent — safe to run repeatedly. The upsert paths in `sync.py` and
`rankings_sync.py` should keep dupes from coming back, but if a new
source surfaces them this fixes the pile-up in one shot.

Usage on the box:
  ssh mobtennis-ubuntu '\
    sudo -u tennismob \
    /opt/tennismob/backend/.venv/bin/python \
    /opt/tennismob/backend/scripts/dedupe_players.py'
"""

from __future__ import annotations

import os
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

from sqlmodel import Session  # noqa: E402

from app.db.session import engine  # noqa: E402
from app.services.player_dedup import (  # noqa: E402
    dedupe_rankings,
    merge_duplicates,
    merge_initial_form_duplicates,
)


def main() -> None:
    with Session(engine) as session:
        # 1. Word-order / token-set duplicates. Catches "Thiago Agustin
        #    Tirante" / "Agustin Tirante Thiago".
        n1 = merge_duplicates(session)
        # 2. Initial-form duplicates. Catches "A. Tabilo" / "Alejandro Tabilo".
        n2 = merge_initial_form_duplicates(session)
        # 3. Whatever ranking-row duplicates earlier merges left behind.
        n3 = dedupe_rankings(session)
    print(f"merged {n1} word-order, {n2} initial-form duplicate player row(s); "
          f"deleted {n3} duplicate ranking row(s)")


if __name__ == "__main__":
    main()
