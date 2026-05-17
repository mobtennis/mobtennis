"""Dry-run the Wikipedia draw scraper for one tournament and report,
per parsed match, exactly why we did/didn't write it.

Categorises failures:
  - bye:               parsed cell was a structural bye (expected to skip)
  - player_unresolved: at least one Wikipedia name we couldn't map to a DB player
  - match_not_found:   both players resolved but no Match row with that pair+round
  - applied:           wrote bracket_position+seeds successfully

Usage:
  sudo -u tennismob /opt/tennismob/backend/.venv/bin/python \\
    /opt/tennismob/backend/scripts/probe_wiki_scrape.py atp rome 2026
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections import Counter
from pathlib import Path


def _load_env() -> None:
    env_file = Path(__file__).resolve().parents[1] / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()

import httpx  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

from app.db.session import engine  # noqa: E402
from app.models.player import Player, Tour  # noqa: E402
from app.models.tournament import Tournament  # noqa: E402
from app.services.draws_wikipedia import (  # noqa: E402
    _apply_draw_shape,
    _extract_bracket_blocks,
    _fetch_wikitext,
    _match_for,
    _parse_bracket_block,
    _resolve_draw_shape,
    _resolve_player,
    _wiki_title_for,
)


async def probe(tour: str, slug: str, year: int) -> None:
    with Session(engine) as session:
        t = session.exec(
            select(Tournament).where(
                Tournament.tour == Tour(tour),
                Tournament.slug == slug,
                Tournament.year == year,
            )
        ).first()
        if t is None:
            print(f"tournament {tour}/{slug}/{year} not in DB")
            return

        title = _wiki_title_for(t, doubles=False)
        if title is None:
            print(f"no SLUG_TO_WIKI_NAME mapping for {slug}")
            return
        print(f"Wikipedia: {title}")

        async with httpx.AsyncClient(headers={"User-Agent": "MobtennisBot/1.0"}) as c:
            wikitext = await _fetch_wikitext(c, title)
        if wikitext is None:
            print("page missing")
            return

        blocks = _extract_bracket_blocks(wikitext)
        parsed = [_parse_bracket_block(b, i) for i, b in enumerate(blocks)]
        parsed = [pb for pb in parsed if pb is not None]
        srun = 0
        for pb in parsed:
            if pb.kind == "section":
                for m in pb.matches:
                    m.section_idx = srun
                srun += 1
        shape = _resolve_draw_shape(parsed)
        if shape is None:
            print("shape resolve failed")
            return

        section_rounds = max(
            (max(b.rd_labels.keys(), default=0) for b in shape.section_blocks), default=0
        )
        tour_players = list(session.exec(select(Player).where(Player.tour == t.tour)).all())

        outcomes: Counter = Counter()
        unresolved_names: list[str] = []
        not_found_pairs: list[str] = []

        for block in shape.section_blocks + (
            [shape.summary_block] if shape.summary_block else []
        ):
            for pm in block.matches:
                if pm.is_bye:
                    outcomes["bye"] += 1
                    continue
                global_round = (
                    pm.rd_index if block.kind == "section"
                    else section_rounds + pm.rd_index
                )
                round_label = shape.label_by_round.get(global_round)
                if not round_label:
                    outcomes["no_round_label"] += 1
                    continue

                p1 = _resolve_player(session, pm.p1_name, t.tour, tour_players) if pm.p1_name else None
                p2 = _resolve_player(session, pm.p2_name, t.tour, tour_players) if pm.p2_name else None
                if p1 is None and p2 is None:
                    outcomes["both_unresolved"] += 1
                    unresolved_names.append(f"{pm.p1_name} / {pm.p2_name}  ({round_label})")
                    continue
                if p1 is None:
                    outcomes["p1_unresolved"] += 1
                    unresolved_names.append(f"{pm.p1_name}  ({round_label})")
                elif p2 is None:
                    outcomes["p2_unresolved"] += 1
                    unresolved_names.append(f"{pm.p2_name}  ({round_label})")

                if p1 is None or p2 is None:
                    continue

                match = _match_for(
                    session, t.id, round_label, False,
                    p1.id if p1 else None, p2.id if p2 else None,
                )
                if match is None:
                    outcomes["match_row_missing"] += 1
                    not_found_pairs.append(
                        f"{round_label}: {p1.full_name} vs {p2.full_name}"
                    )
                else:
                    outcomes["applied"] += 1

        print()
        print("Outcomes:")
        for k, v in outcomes.most_common():
            print(f"  {k:22} {v}")
        print()
        print(f"Unresolved player names ({len(unresolved_names)}):")
        for name in unresolved_names[:30]:
            print(f"  - {name}")
        if len(unresolved_names) > 30:
            print(f"  ... +{len(unresolved_names) - 30} more")
        print()
        print(f"Match-row missing ({len(not_found_pairs)}):")
        for line in not_found_pairs[:30]:
            print(f"  - {line}")
        if len(not_found_pairs) > 30:
            print(f"  ... +{len(not_found_pairs) - 30} more")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("usage: probe_wiki_scrape.py <tour> <slug> <year>")
        sys.exit(1)
    asyncio.run(probe(sys.argv[1], sys.argv[2], int(sys.argv[3])))
