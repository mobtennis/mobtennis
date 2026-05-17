"""Derive per-match statistics from api-tennis `pointbypoint` payload.

api-tennis ships a structured point history per match (fixtures + livescore
endpoints). It looks like:

  pointbypoint: [
    { set_number: "Set 1", number_game: "1",
      player_served: "Second Player",
      serve_winner: "Second Player",   # who won this game
      serve_lost: null | "First Player" | "Second Player",
      score: "0 - 1",                  # game score in this set after game
      points: [ { number_point: "1", score: "0 - 15",
                  break_point, set_point, match_point } ... ] }
    ...
  ]

We don't get aces / unforced errors — those need a richer stats endpoint we
don't have. But we can compute the table-stakes service-game / break-point
stats from this alone, and that's a meaningful upgrade over plain score.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class PlayerStats:
    service_games_won: int = 0
    service_games_played: int = 0
    break_points_won: int = 0     # opportunities converted as the returner
    break_points_total: int = 0   # opportunities seen as the returner
    points_won: int = 0


@dataclass
class MatchStats:
    player1: PlayerStats
    player2: PlayerStats


_FIRST = "First Player"
_SECOND = "Second Player"


def compute_stats(pointbypoint: list | None) -> dict | None:
    """Return MatchStats as a plain dict, or None if input is empty.

    Idempotent: pure function over the input, no side effects.
    """
    if not pointbypoint:
        return None

    p1 = PlayerStats()
    p2 = PlayerStats()

    for game in pointbypoint:
        served = game.get("player_served")
        winner = game.get("serve_winner")

        if served == _FIRST:
            p1.service_games_played += 1
            if winner == _FIRST:
                p1.service_games_won += 1
        elif served == _SECOND:
            p2.service_games_played += 1
            if winner == _SECOND:
                p2.service_games_won += 1

        # Break points are evaluated point-by-point: the returner is the
        # *opposite* of player_served. A break_point flag means the returner
        # has a chance to break — if the game's winner is the returner, the
        # last bp converted (we count that as one conversion per game with
        # at least one bp opportunity). Multiple bps in the same game still
        # count as one conversion if the game ends with a break.
        had_bp_for_p1 = had_bp_for_p2 = False
        for pt in game.get("points") or []:
            if not pt.get("break_point"):
                continue
            if served == _SECOND:
                had_bp_for_p1 = True
            elif served == _FIRST:
                had_bp_for_p2 = True

        if had_bp_for_p1:
            p1.break_points_total += 1
            if winner == _FIRST:
                p1.break_points_won += 1
        if had_bp_for_p2:
            p2.break_points_total += 1
            if winner == _SECOND:
                p2.break_points_won += 1

        # Total points: walk the points and count whose score advanced. The
        # api ships running per-point scores like "0 - 15" → "15 - 15" — we
        # just compare consecutive entries.
        prev = (0, 0)
        for pt in game.get("points") or []:
            score = pt.get("score") or ""
            cur = _parse_point_score(score)
            if cur is None:
                continue
            if cur[0] > prev[0]:
                p1.points_won += 1
            elif cur[1] > prev[1]:
                p2.points_won += 1
            prev = cur

    return {"player1": asdict(p1), "player2": asdict(p2)}


def _parse_point_score(s: str) -> tuple[int, int] | None:
    """Parse a point score like '0 - 15', '30 - 40', '15 - AD'.

    Returns a comparable tuple where AD > 40 > 30 > 15 > 0. Used only for
    detecting *which side* incremented across consecutive points; the exact
    tennis-scoring math doesn't matter, only the rank ordering.
    """
    parts = s.split("-")
    if len(parts) != 2:
        return None

    def rank(p: str) -> int | None:
        p = p.strip().upper()
        if p == "AD":
            return 50
        if p.isdigit():
            return int(p)
        return None

    a, b = rank(parts[0]), rank(parts[1])
    if a is None or b is None:
        return None
    return a, b
