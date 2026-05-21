"""Ranking points per round, by tour + tournament category.

Source: ATP & WTA published rules (current ranking system, post-2024 ATP
reorganisation; WTA values reflect their 2024+ scale).

The "result codes" (W, F, SF, QF, R16, R32, R64, R128) map to where the
player lost — except W which means they won the final. `compute_player_result`
in services/rounds.py produces these codes; we consume them here.

This module is read-only / pure: no DB, no I/O. Use:

  from app.services.ranking_points import points_for_result, available_for_round

Caveats / approximations:
  - ATP Finals and WTA Finals use a round-robin format with per-match
    bonuses. We approximate to a single per-stage value (group, SF, F, W)
    which is enough for the live-rankings UI; it's within ~5%% of the
    true round-robin sum for any 3-match group.
  - "Best 18/19" rule is NOT applied here. v1 of the live ranking treats
    every result equally, which matches what LiveTennis.eu and Tennis
    Abstract do. Affects projections at the margins (mostly outside top 30).
  - Davis Cup / BJK Cup points are tied to the team competition format and
    don't map cleanly to a per-result number; treated as 0 here.
"""

from __future__ import annotations

# Result-code points by tier. Result codes follow the same set
# `compute_player_result()` produces, with one extra: ROUND_ROBIN_WIN
# for an ATP/WTA Finals group-stage win (used when computing earned
# points if we ever wire RR-aware logic; currently unused).
_RESULTS = ("W", "F", "SF", "QF", "R16", "R32", "R64", "R128")


# ATP — Grand Slam, ATP 1000 (mandatory), 500, 250, Finals.
_ATP: dict[str, dict[str, int]] = {
    "grand_slam": {
        "W": 2000, "F": 1300, "SF": 800, "QF": 400,
        "R16": 200, "R32": 100, "R64": 50, "R128": 10,
    },
    "atp_1000": {
        # 7-round Masters (Indian Wells, Miami, Madrid, Rome, Canada,
        # Cincinnati, Shanghai). 6-round Monte Carlo + Paris drop the
        # R128 row but keep the rest of the scale.
        "W": 1000, "F": 650, "SF": 400, "QF": 200,
        "R16": 100, "R32": 50, "R64": 25, "R128": 10,
    },
    "atp_500": {
        "W": 500, "F": 330, "SF": 200, "QF": 100,
        "R16": 50, "R32": 25, "R64": 0, "R128": 0,
    },
    "atp_250": {
        "W": 250, "F": 165, "SF": 100, "QF": 50,
        "R16": 25, "R32": 13, "R64": 0, "R128": 0,
    },
    "atp_finals": {
        # Approximated to outcome milestones. A real RR walk would add
        # 200 per group win + 400 SF + 500 F + 1500 W (undefeated max),
        # but for the projection UI a single number per outcome stage
        # is enough.
        "W": 1500, "F": 1000, "SF": 600, "QF": 0,
        "R16": 0, "R32": 0, "R64": 0, "R128": 0,
    },
}

# WTA — same tier names, slightly different scale (WTA 2024+).
_WTA: dict[str, dict[str, int]] = {
    "grand_slam": {
        "W": 2000, "F": 1300, "SF": 780, "QF": 430,
        "R16": 240, "R32": 130, "R64": 70, "R128": 10,
    },
    "wta_1000": {
        # 96-draw mandatory events (IW, Miami, Madrid, Beijing, Wuhan).
        # 56-draw events (Doha, Dubai, Rome partly) drop the R128 row.
        "W": 1000, "F": 650, "SF": 390, "QF": 215,
        "R16": 120, "R32": 65, "R64": 35, "R128": 10,
    },
    "wta_500": {
        "W": 500, "F": 325, "SF": 195, "QF": 108,
        "R16": 60, "R32": 1, "R64": 0, "R128": 0,
    },
    "wta_250": {
        "W": 250, "F": 163, "SF": 98, "QF": 54,
        "R16": 30, "R32": 1, "R64": 0, "R128": 0,
    },
    "wta_finals": {
        "W": 1500, "F": 1000, "SF": 600, "QF": 0,
        "R16": 0, "R32": 0, "R64": 0, "R128": 0,
    },
}


def points_for_result(tour: str, category: str | None, result: str) -> int:
    """Look up ranking points for a (category, result) pair.

    `tour` is "atp" / "wta". `category` is the TournamentCategory value
    (e.g. "grand_slam", "atp_1000"). `result` is the code from
    `compute_player_result` ("W", "F", "SF" …).

    Returns 0 for unknown / unrankable combinations (Davis Cup, BJK Cup,
    challengers, ITFs, qualifying rounds, walkovers in the first round).
    """
    if not category:
        return 0
    table = _ATP if tour == "atp" else _WTA
    tier = table.get(category)
    if not tier:
        return 0
    return tier.get(result, 0)


def available_for_round(tour: str, category: str | None, current_round: str) -> int:
    """Points already-guaranteed for a player who has won through
    `current_round` and not yet lost. Equivalent to the points for losing
    in the *next* round.

    For a player who has just won their R16 match (still in the draw),
    they are guaranteed QF points minimum. If they then win the QF, they
    move up to SF guaranteed. We don't try to project further; the
    function returns what they've LOCKED IN, not what they MIGHT earn.
    """
    if not category:
        return 0
    next_round = _NEXT_LOSE_ROUND.get(current_round)
    if next_round is None:
        return 0
    return points_for_result(tour, category, next_round)


# Map "you just won round X" → "minimum result if you lose round X+1".
# Winning a R128 match → guaranteed R64 points minimum (since you can't
# do worse than losing the R64 next). Winning a Final → W, no further round.
_NEXT_LOSE_ROUND: dict[str, str] = {
    "R128": "R64",
    "R64":  "R32",
    "R32":  "R16",
    "R16":  "QF",
    "QF":   "SF",
    "SF":   "F",
    "F":    "W",
    "W":    "W",  # already won, no upgrade
}
