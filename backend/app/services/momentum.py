"""Compute a match *momentum* series from api-tennis `pointbypoint`.

Momentum is a recency-weighted local swing — "who has the wind at their back
right now" — signed toward player1 (positive) vs player2 (negative). It is
deliberately distinct from win-probability: a player can be behind on the
scoreboard yet carry all the momentum (the moment a comeback is born).

Input is the same `pointbypoint` array we already parse for stats
(`app/services/match_stats.py`): a list of games, each

    { set_number: "Set 1", number_game: "1",
      player_served: "First Player", serve_winner: "First Player",
      serve_lost: null, score: "1 - 0",
      points: [ { score: "0 - 15", break_point, set_point, match_point } ... ] }

The model (all weights tunable):

  * each game contributes a signed weight to a running total
  * the total decays each game (LAMBDA) so momentum stays *local*
  * the series is normalised to -100..+100 for display

Weights reward what actually turns matches — breaking serve, breaking back,
surviving break/set/championship points — far above a routine hold.
"""

from __future__ import annotations

_FIRST = "First Player"
_SECOND = "Second Player"

# --- Model constants (tunable) ------------------------------------------------
LAMBDA = 0.75  # per-game decay; lower = more local/twitchy

W_HOLD = 2.0
W_HOLD_SAVE_BP = 4.0      # held after facing break point(s)
W_HOLD_SAVE_SP = 5.0      # held after facing set point(s)
W_HOLD_SAVE_MP = 7.0      # held after facing match/championship point(s) — huge
W_BREAK = 6.0
W_BREAK_BACK = 8.0        # broke straight back after being broken
W_SET = 12.0
W_SET_TB = 14.0           # set decided in a tiebreak — more dramatic


def _parse_set_no(s: str | None) -> int:
    """'Set 1' -> 1. Falls back to 1 on anything unexpected."""
    if not s:
        return 1
    digits = "".join(ch for ch in s if ch.isdigit())
    return int(digits) if digits else 1


def _game_score(s: str | None) -> tuple[int, int] | None:
    """'6 - 4' -> (6, 4). None if unparseable."""
    if not s or "-" not in s:
        return None
    a, _, b = s.partition("-")
    try:
        return int(a.strip()), int(b.strip())
    except ValueError:
        return None


def compute_momentum(
    pointbypoint: list | None,
    *,
    complete: bool = True,
    first_is_player1: bool = True,
) -> dict | None:
    """Return a momentum payload, or None if there's nothing to compute.

    ``complete`` marks whether the match is over. When True the final game in
    the data closes its set (so it earns the set/match weight); when False
    (a live match) the trailing in-progress set is not treated as won.

    ``first_is_player1`` orients the output to *our* match.player1. api-tennis
    labels players "First"/"Second"; when our player1 is api-tennis's Second
    Player (common for Sackmann-imported historical rows), pass False and the
    whole series is flipped so positive momentum always means our player1.

    Shape:
      { "series": [ {i,set,score,server,winner,is_break,kind,m}, ... ],
        "events": [ {i,set,score,winner,kind,label,swing}, ... ],
        "final": float,            # last momentum value, -100..+100
        "leader": 1|2|0,           # who momentum favours at the end
        "n_games": int }
    """
    if not pointbypoint:
        return None

    # 1. Parse each game into flat facts.
    parsed: list[dict] = []
    for g in pointbypoint:
        served = g.get("player_served")
        winner = g.get("serve_winner")
        if served not in (_FIRST, _SECOND) or winner not in (_FIRST, _SECOND):
            continue  # skip malformed / not-yet-started rows
        pts = g.get("points") or []
        parsed.append({
            "set_no": _parse_set_no(g.get("set_number")),
            "served": served,
            "winner": winner,
            "score": (g.get("score") or "").strip(),
            "is_break": winner != served,
            "had_bp": any(p.get("break_point") for p in pts),
            "had_sp": any(p.get("set_point") for p in pts),
            "had_mp": any(p.get("match_point") for p in pts),
        })
    if not parsed:
        return None

    n = len(parsed)

    def is_set_end(i: int) -> bool:
        if i == n - 1:
            return complete  # final game closes its set only if match is over
        return parsed[i + 1]["set_no"] != parsed[i]["set_no"]

    def set_was_tiebreak(i: int) -> bool:
        sc = _game_score(parsed[i]["score"])
        # 7-6 (or 6-7) is a tiebreak set; the deciding super-tiebreak final
        # set also lands on a 7-6 game score in this feed.
        return bool(sc) and {sc[0], sc[1]} == {6, 7}

    # 2. Walk games, accrue decayed momentum.
    m = 0.0
    series: list[dict] = []
    prev_break_by: str | None = None

    for i, p in enumerate(parsed):
        winner = p["winner"]
        is_break = p["is_break"]

        if is_break:
            if prev_break_by and prev_break_by != winner:
                weight, kind = W_BREAK_BACK, "break_back"
            else:
                weight, kind = W_BREAK, "break"
        else:
            # A hold. Reward surviving pressure — but a set/match point *inside*
            # a set-ending hold is the server converting their own, handled by
            # the set weight below, so only credit "saved" on non-set-end holds.
            if not is_set_end(i) and p["had_mp"]:
                weight, kind = W_HOLD_SAVE_MP, "hold_save_mp"
            elif not is_set_end(i) and p["had_sp"]:
                weight, kind = W_HOLD_SAVE_SP, "hold_save_sp"
            elif p["had_bp"]:
                weight, kind = W_HOLD_SAVE_BP, "hold_save_bp"
            else:
                weight, kind = W_HOLD, "hold"

        if is_set_end(i):
            weight += W_SET_TB if set_was_tiebreak(i) else W_SET
            kind = ("set_tb" if set_was_tiebreak(i) else "set") + ("_break" if is_break else "")

        signed = weight if winner == _FIRST else -weight
        m = m * LAMBDA + signed

        series.append({
            "i": i,
            "set": p["set_no"],
            "score": p["score"],
            "server": 1 if p["served"] == _FIRST else 2,
            "winner": 1 if winner == _FIRST else 2,
            "is_break": is_break,
            "kind": kind,
            "_raw": m,
        })
        prev_break_by = winner if is_break else None

    # 3. Normalise to -100..+100 by the match's own peak.
    peak = max((abs(s["_raw"]) for s in series), default=1.0) or 1.0
    prev_m = 0.0
    for s in series:
        s["m"] = round(100.0 * s["_raw"] / peak, 1)
        s["_swing"] = round(s["m"] - prev_m, 1)
        prev_m = s["m"]
        del s["_raw"]

    # 4. Notable events (breaks, clutch saves, set ends) for the narrative UI.
    events = [
        {
            "i": s["i"], "set": s["set"], "score": s["score"],
            "winner": s["winner"], "kind": s["kind"],
            "swing": s["_swing"],
        }
        for s in series
        if s["kind"] != "hold"
    ]
    for s in series:
        del s["_swing"]

    # 5. Orient to our player1 (flip sign / swap player refs if needed).
    if not first_is_player1:
        _swap = {1: 2, 2: 1}
        for s in series:
            s["m"] = -s["m"]
            s["server"] = _swap[s["server"]]
            s["winner"] = _swap[s["winner"]]
        for e in events:
            e["winner"] = _swap[e["winner"]]
            e["swing"] = -e["swing"]

    final = series[-1]["m"]
    leader = 1 if final > 4 else (2 if final < -4 else 0)

    return {
        "series": series,
        "events": events,
        "final": final,
        "leader": leader,
        "n_games": n,
    }
