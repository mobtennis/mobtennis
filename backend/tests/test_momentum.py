"""Tests for the momentum model (app/services/momentum.py)."""

from __future__ import annotations

from app.services.momentum import compute_momentum

_F = "First Player"
_S = "Second Player"


def _game(set_no, served, winner, score, *, bp=False, sp=False, mp=False):
    return {
        "set_number": f"Set {set_no}",
        "player_served": served,
        "serve_winner": winner,
        "score": score,
        "points": [{"score": "40 - 30", "break_point": bp, "set_point": sp, "match_point": mp}],
    }


def test_empty_returns_none():
    assert compute_momentum(None) is None
    assert compute_momentum([]) is None


def test_holds_and_break_favour_first_player():
    pbp = [
        _game(1, _F, _F, "1 - 0"),   # P1 hold
        _game(1, _S, _F, "2 - 0"),   # P1 break — big
    ]
    out = compute_momentum(pbp, complete=False)
    assert out is not None
    assert out["series"][-1]["m"] > 0          # momentum toward player1
    assert out["series"][1]["is_break"] is True
    assert out["series"][1]["kind"] == "break"


def test_break_back_detected():
    pbp = [
        _game(1, _S, _F, "1 - 0"),   # P1 breaks
        _game(1, _F, _S, "1 - 1"),   # P2 breaks straight back
    ]
    out = compute_momentum(pbp, complete=False)
    assert out["series"][1]["kind"] == "break_back"
    assert out["series"][1]["winner"] == 2


def test_orientation_flip_negates():
    pbp = [_game(1, _F, _F, "1 - 0"), _game(1, _S, _F, "2 - 0")]
    a = compute_momentum(pbp, complete=False, first_is_player1=True)
    b = compute_momentum(pbp, complete=False, first_is_player1=False)
    assert a["series"][-1]["m"] == -b["series"][-1]["m"]
    # winner refs swap too
    assert a["series"][-1]["winner"] == 1
    assert b["series"][-1]["winner"] == 2


def test_set_end_adds_weight_and_is_flagged():
    # A set-ending game should swing far more than a mid-set hold.
    mid = compute_momentum(
        [_game(1, _F, _F, "1 - 0"), _game(1, _S, _S, "1 - 1")], complete=False
    )
    setend = compute_momentum(
        [_game(1, _F, _F, "5 - 4"), _game(1, _S, _F, "6 - 4")], complete=True
    )
    assert setend["series"][-1]["kind"].startswith("set")
    # normalised, but the set-winner ends near the top of the scale
    assert setend["series"][-1]["m"] > 90


def test_tiebreak_rows_collapse_to_one_event():
    # api-tennis lists a set's games under "Set 1" (with a summary "7 - 6"
    # row for a TB-decided set) AND the tiebreak points under "Set 1
    # TieBreak". The point rows must be dropped, and the decider must read as
    # a single tiebreak event — not a break, and not one game per TB point.
    pbp = [
        _game(1, _F, _F, "6 - 6"),          # into the breaker at 6-6
        # tiebreak points — should ALL be skipped
        {"set_number": "Set 1 TieBreak", "player_served": _F, "serve_winner": _F,
         "score": "1 - 0", "points": []},
        {"set_number": "Set 1 TieBreak", "player_served": _S, "serve_winner": _F,
         "score": "7 - 5", "points": []},
        _game(1, _S, _F, "7 - 6"),          # summary decider row (F wins TB)
    ]
    out = compute_momentum(pbp, complete=True)
    assert out["n_games"] == 2                      # only the two real games
    decider = out["series"][-1]
    assert decider["kind"] == "set_tb"
    assert decider["is_break"] is False             # a TB is not a break
    # no TieBreak point rows leaked in
    assert all("tiebreak" not in s["score"].lower() for s in out["series"])
    # and no phantom breaks were recorded for TB points
    assert len([e for e in out["events"] if e["kind"] == "break"]) == 0


def test_clutch_hold_beats_plain_hold():
    plain = compute_momentum([_game(1, _F, _F, "1 - 0")], complete=False)
    clutch = compute_momentum([_game(1, _F, _F, "1 - 0", mp=True)], complete=False)
    # both normalise to their own peak (single game), so check the kind label
    assert plain["series"][0]["kind"] == "hold"
    assert clutch["series"][0]["kind"] == "hold_save_mp"
