"""Tournament round normalization.

api-tennis emits round strings like "ATP Rome - 1/64-finals". For our purposes
we need:
  - depth weight (so we can sort and find the deepest round a player reached)
  - short abbreviation (R128, QF, F, ...) for the UI
"""

from __future__ import annotations

# Higher = later in the tournament. Keeps the deepest-reached calculation
# cheap (just max() on this score).
_ROUND_DEPTH: dict[str, int] = {
    "final": 100, "f": 100,
    "semi-finals": 90, "1/2-finals": 90, "sf": 90, "semifinals": 90,
    "quarter-finals": 80, "1/4-finals": 80, "qf": 80, "quarterfinals": 80,
    "1/8-finals": 70, "r16": 70, "round of 16": 70, "fourth round": 70,
    "1/16-finals": 60, "r32": 60, "third round": 60,
    "1/32-finals": 50, "r64": 50, "second round": 50,
    "1/64-finals": 40, "r128": 40, "first round": 40, "round 1": 40,
    "1/128-finals": 30, "r256": 30,
    "qualification round 3": 25, "qualifying 3": 25, "q3": 25,
    "qualification round 2": 20, "qualifying 2": 20, "q2": 20,
    "qualification round 1": 15, "qualifying 1": 15, "q1": 15,
    "qualification": 10, "qualifying": 10, "q": 10,
}

_ROUND_ABBREV: dict[str, str] = {
    "final": "F", "f": "F",
    "1/2-finals": "SF", "semi-finals": "SF", "sf": "SF", "semifinals": "SF",
    "1/4-finals": "QF", "quarter-finals": "QF", "qf": "QF", "quarterfinals": "QF",
    "1/8-finals": "R16", "round of 16": "R16", "fourth round": "R16",
    "1/16-finals": "R32", "third round": "R32",
    "1/32-finals": "R64", "second round": "R64",
    "1/64-finals": "R128", "first round": "R128", "round 1": "R128",
    "1/128-finals": "R256",
    "qualification": "Q", "qualifying": "Q",
}


def _strip_prefix(round_str: str) -> str:
    """api-tennis prefixes the round with the tournament name. Drop it."""
    last_dash = round_str.rfind(" - ")
    return round_str[last_dash + 3:] if last_dash >= 0 else round_str


def round_depth(round_str: str | None) -> int:
    if not round_str:
        return 0
    return _ROUND_DEPTH.get(_strip_prefix(round_str).lower().strip(), 0)


def round_abbrev(round_str: str | None) -> str:
    if not round_str:
        return ""
    tail = _strip_prefix(round_str).strip()
    return _ROUND_ABBREV.get(tail.lower(), tail)


def compute_player_result(deepest_round: str | None, won_deepest: bool) -> str:
    """Map (deepest round reached, did they win that match?) → result code.

    Convention:
      W   = won the title (won the Final)
      F   = lost the Final (runner-up)
      SF  = lost in the semis
      QF, R16, R32, R64, R128 = lost in that round
      Q   = lost in qualifying
    """
    abbrev = round_abbrev(deepest_round)
    if abbrev == "F" and won_deepest:
        return "W"
    return abbrev or "—"
