"""Dump the parsed structure of a Wikipedia bracket page.

Usage:
    python scripts/parse_wiki_bracket.py "2026 Italian Open – Men's singles"
    python scripts/parse_wiki_bracket.py "2025 French Open – Men's singles" --summary
    python scripts/parse_wiki_bracket.py "..." --json > out.json

The default output is a human-readable per-round dump; --summary prints
only counts and warnings; --json emits structured JSON for diffing.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from collections import defaultdict
from pathlib import Path

# Make `app.*` importable when run from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.wiki_brackets import parse_page  # noqa: E402


def _readable(parsed) -> str:
    out: list[str] = []
    out.append(f"page:          {parsed.page_title}")
    out.append(f"draw_size:     {parsed.draw_size}")
    out.append(f"sections:      {parsed.section_count} × {parsed.slots_per_section} slots")
    out.append(f"round_names:   {' → '.join(parsed.round_names)}")
    if parsed.warnings:
        out.append("warnings:")
        for w in parsed.warnings:
            out.append(f"  - {w}")
    by_round: dict[str, list] = defaultdict(list)
    for m in parsed.matches:
        by_round[m.round_name].append(m)
    out.append("")
    for round_name in parsed.round_names:
        matches = by_round.get(round_name, [])
        played = [m for m in matches if not m.is_bye]
        out.append(f"== {round_name} ({len(played)} played / {len(matches)} slots) ==")
        for m in sorted(matches, key=lambda x: x.bracket_position):
            if m.is_bye:
                out.append(f"  [{m.bracket_position:>3}] (bye)")
                continue
            t1 = _short(m.team1)
            t2 = _short(m.team2)
            score = m.score or "—"
            section = f" §{m.raw_section}" if m.raw_section else ""
            out.append(f"  [{m.bracket_position:>3}]{section}  {t1:<30} vs {t2:<30}  {score}")
        out.append("")
    return "\n".join(out)


def _short(p) -> str:
    if p is None:
        return "—"
    name = p.wikilink or p.display_name or "?"
    seed = f"[{p.seed}]" if p.seed else ""
    mark = "✓" if p.won else " "
    return f"{mark} {seed:<5} {name}".strip()


def _to_dict(parsed) -> dict:
    """Flatten to plain Python so json.dumps works."""
    d = dataclasses.asdict(parsed)
    # round_names is a tuple — JSON-fine but be explicit.
    d["round_names"] = list(d["round_names"])
    return d


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("page_title", help="Wikipedia page title")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of human-readable text")
    parser.add_argument("--summary", action="store_true", help="counts + warnings only")
    args = parser.parse_args()
    parsed = parse_page(args.page_title)
    if args.summary:
        print(f"{parsed.page_title}: draw={parsed.draw_size}, "
              f"sections={parsed.section_count}×{parsed.slots_per_section}, "
              f"matches={len(parsed.matches)}, "
              f"played={sum(1 for m in parsed.matches if not m.is_bye)}, "
              f"warnings={len(parsed.warnings)}")
        for w in parsed.warnings:
            print(f"  warning: {w}")
        return 0
    if args.json:
        print(json.dumps(_to_dict(parsed), indent=2, ensure_ascii=False))
        return 0
    print(_readable(parsed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
