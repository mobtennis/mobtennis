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


# Tokens that unambiguously mean a qualifying-bracket round. The
# verbose-final-collision issue called out elsewhere in this module
# (api-tennis labels qualifying-bracket finals as "- Final" same as
# main-draw finals) is NOT relevant here — we only care whether the
# round string starts with a qualifying marker like "Qualifying 1"
# or "Q3". Main-draw rounds never carry these prefixes.
_QUALIFYING_TOKENS = (
    "qualifying",
    "qualification",
    "qualifier",  # "ATP Wimbledon - Qualifiers" variant
    "q1", "q2", "q3", "q4",
)


def is_qualifying_round(round_str: str | None) -> bool:
    """True if the round string represents a match in the qualifying
    bracket — used by the tournament index to label a tournament as
    "in qualifying phase" when every running match is a Q-round.
    """
    if not round_str:
        return False
    tail = _strip_prefix(round_str).strip().lower()
    return any(tail.startswith(tok) for tok in _QUALIFYING_TOKENS)


# Short-code rounds that ONLY get emitted for main-draw matches.
# Our Sackmann + Wikipedia bracket parsers use these; api-tennis only
# emits verbose labels (which conflate qualifying with main draw).
# An R128/R64/etc. in the data is an authoritative "main draw is
# underway" signal — useful when the tournament's start_date is one
# day off (e.g. Wimbledon 2026 stored as 06-30 but Day 1 was 06-29).
_MAIN_DRAW_SHORT_CODES = frozenset({
    "r256", "r128", "r64", "r32", "r16", "qf", "sf", "f",
})


def is_main_draw_short_code(round_str: str | None) -> bool:
    """True if the round string is one of our unambiguous main-draw
    short codes. Authoritative — only the main-draw parsers emit
    these, qualifying records are always verbose."""
    if not round_str:
        return False
    return round_str.strip().lower() in _MAIN_DRAW_SHORT_CODES


def select_deepest_match(matches):
    """Pick the match representing the deepest round a player reached,
    avoiding the qualifying-bracket conflation that plagues api-tennis
    verbose round labels.

    The bug pattern: api-tennis labels every qualifying-bracket round
    verbosely as "ATP <Tournament> - Quarter-finals" / "- Semi-finals" /
    "- Final" even though qualifying is only 3 rounds. After
    `_strip_prefix` those become "Quarter-finals" / "Semi-finals" /
    "Final" with the same round_depth as their main-draw equivalents.
    Naïve max-by-depth over a qualifier's matches at a Slam would
    return their Q-final win (depth 100) and report them as the
    tournament winner.

    Two-tier strategy:
      1. If the player has ANY short-code matches at this tournament
         (R128, R64, …, QF, SF, F — Sackmann / Wikipedia convention),
         restrict to those. Main-draw participation always produces a
         short-code record, so this captures the true deepest reach
         and ignores the parallel verbose Q-bracket records.
      2. Otherwise — typical of Challenger / ITF tournaments where
         api-tennis is our only data source and there are no
         qualifying records to conflate — fall back to the max-depth
         over the verbose-only set.

    Returns the chosen Match-like object or None if `matches` is empty.
    """
    if not matches:
        return None
    short = [
        m for m in matches
        if getattr(m, "round", None) and " - " not in m.round
    ]
    if short:
        # Among short codes, prefer "F" outright (main-draw final), else
        # the deepest by depth weight.
        for m in short:
            if m.round == "F":
                return m
        return max(short, key=lambda m: round_depth(m.round))
    # All-verbose set — no main-draw / qualifying ambiguity to worry
    # about because we don't have a parallel main-draw record.
    return max(matches, key=lambda m: round_depth(getattr(m, "round", None)))


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
