"""Apply a parsed Wikipedia bracket to our DB for one tournament.

Usage:
    python scripts/apply_wiki_bracket.py \
        --tour atp --slug rome --year 2026 \
        --page "2026 Italian Open – Men's singles" \
        [--nuke] [--dry-run]

  --nuke      Delete non-Sackmann singles matches for the tournament
              before applying. Use when the existing data is broken.
              Sackmann-sourced rows are preserved.
  --dry-run   Parse + report unresolved players + a summary, but don't
              commit. Useful for growing the overrides table.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlmodel import Session, select  # noqa: E402

from app.db.session import engine  # noqa: E402
from app.models.player import Tour  # noqa: E402
from app.models.tournament import Tournament  # noqa: E402
from app.services.wiki_brackets import parse_page  # noqa: E402
from app.services.wiki_brackets_apply import apply_parsed_bracket  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tour", required=True, choices=["atp", "wta"])
    ap.add_argument("--slug", required=True, help="tournament slug, e.g. 'rome'")
    ap.add_argument("--year", required=True, type=int)
    ap.add_argument("--page", required=True, help="Wikipedia page title")
    ap.add_argument("--nuke", action="store_true",
                    help="delete non-Sackmann singles matches before applying")
    ap.add_argument("--dry-run", action="store_true",
                    help="parse + report, don't commit")
    args = ap.parse_args()

    tour_enum = Tour.ATP if args.tour == "atp" else Tour.WTA

    with Session(engine) as session:
        t = session.exec(
            select(Tournament).where(
                Tournament.slug == args.slug,
                Tournament.year == args.year,
                Tournament.tour == tour_enum,
            )
        ).first()
        if t is None:
            print(f"Tournament not found: {args.tour}/{args.slug}/{args.year}",
                  file=sys.stderr)
            return 1

        print(f"Tournament: {t.tour.value}/{t.slug}/{t.year} (id={t.id}, '{t.name}')")
        print(f"Fetching Wikipedia page: {args.page}")
        parsed = parse_page(args.page)
        print(f"Parsed: draw={parsed.draw_size}, "
              f"sections={parsed.section_count}×{parsed.slots_per_section}, "
              f"matches={len(parsed.matches)} "
              f"({sum(1 for m in parsed.matches if not m.is_bye)} played)")
        if parsed.warnings:
            for w in parsed.warnings:
                print(f"  warning: {w}")

        result = apply_parsed_bracket(
            session, t, parsed, nuke_first=args.nuke,
        )
        print()
        print(result.summary())

        if result.unresolved:
            print()
            # Stable, deduplicated list — easier to copy into the overrides table.
            seen: set[str] = set()
            print("Unresolved players (Wikipedia title → slug we tried):")
            for wiki, slug in sorted(result.unresolved):
                if wiki in seen:
                    continue
                seen.add(wiki)
                print(f"  {wiki!r:60} → {slug!r}")
            print(f"\n  ({len(seen)} distinct unresolved titles)")

        if args.dry_run:
            session.rollback()
            print("\n--dry-run: rolled back, no DB changes.")
        else:
            session.commit()
            print("\nCommitted.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
