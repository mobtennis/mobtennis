"""Match-state diffing for push notifications.

The detector runs inside the live-poll upsert path. For each updated match we
hold the *old* match row in memory, then compare against the incoming
LiveMatch payload to decide what events to emit. We keep this self-contained
so the rest of the codebase doesn't carry score-parsing knowledge.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

EventKind = Literal[
    "match_start",
    "match_end",
    "set_end",
    "tiebreak_start",
    "break_of_serve",
    "game_end",
]

# Events that fire under the "key_moments" granularity. "game_end" is only
# delivered to followers who opted into "every_game".
KEY_MOMENT_KINDS: set[str] = {
    "match_start",
    "match_end",
    "set_end",
    "tiebreak_start",
    "break_of_serve",
}


@dataclass
class MatchEvent:
    match_id: int
    kind: EventKind
    title: str
    body: str


def _parse_score(score: str | None) -> list[tuple[int, int]]:
    """Parse "6-4 7-6(5) 3-6" → [(6,4), (7,6), (3,6)]. Tiebreak digits inside
    parens are stripped — they're cosmetic for diff purposes."""
    if not score:
        return []
    sets: list[tuple[int, int]] = []
    for tok in score.split():
        if "-" not in tok:
            continue
        a, _, b = tok.partition("-")
        a = a.split("(", 1)[0]
        b = b.split("(", 1)[0]
        try:
            sets.append((int(a), int(b)))
        except ValueError:
            continue
    return sets


def _has_tiebreak_marker(score: str | None, set_index: int) -> bool:
    """Did the set at `set_index` (0-based) contain a (N) tiebreak suffix?"""
    if not score:
        return False
    toks = score.split()
    if set_index >= len(toks):
        return False
    return "(" in toks[set_index]


def _at_tiebreak_score(set_pair: tuple[int, int]) -> bool:
    """6-6 in a non-final set means a tiebreak is starting/in progress."""
    return set_pair == (6, 6)


def detect_events(
    match_id: int,
    old_status: str,
    old_score: str | None,
    old_server_id: int | None,
    new_status: str,
    new_score: str | None,
    p1_id: int | None,
    p2_id: int | None,
    p1_name: str,
    p2_name: str,
) -> list[MatchEvent]:
    events: list[MatchEvent] = []
    old_sets = _parse_score(old_score)
    new_sets = _parse_score(new_score)

    # Match start: anything → live
    if old_status != "live" and new_status == "live":
        events.append(MatchEvent(
            match_id=match_id,
            kind="match_start",
            title="Match underway",
            body=f"{p1_name} vs {p2_name} has begun.",
        ))

    # Match end: live → terminal
    if old_status == "live" and new_status in ("finished", "retired", "walkover"):
        winner_name = None
        if new_sets:
            # Determine winner by sets won
            p1_won = sum(1 for a, b in new_sets if a > b)
            p2_won = sum(1 for a, b in new_sets if b > a)
            if p1_won > p2_won:
                winner_name = p1_name
            elif p2_won > p1_won:
                winner_name = p2_name
        score_str = new_score or ""
        if new_status == "retired":
            body = f"{p1_name} vs {p2_name} — retired. {score_str}".strip()
        elif new_status == "walkover":
            body = f"{p1_name} vs {p2_name} — walkover."
        elif winner_name:
            body = f"{winner_name} wins. {score_str}".strip()
        else:
            body = f"{p1_name} vs {p2_name} — final. {score_str}".strip()
        events.append(MatchEvent(
            match_id=match_id, kind="match_end", title="Match finished", body=body,
        ))

    # Per-set diffs
    if new_status == "live":
        # Set ended: a brand-new set entry appeared
        if len(new_sets) > len(old_sets):
            # The just-completed set is at index len(new_sets) - 2 (the one
            # before the freshly-opened current set), or new_sets[-1] if the
            # match completed in this same poll. We pick the last *closed* set.
            closed_idx = len(new_sets) - 1
            # If status is still live, the last entry is the just-closed set.
            # If a new set has already opened (rare in one poll), it'd be at -1
            # too — close enough for v1.
            a, b = new_sets[closed_idx]
            leader_name = p1_name if a > b else p2_name if b > a else None
            sets_a = sum(1 for x, y in new_sets if x > y)
            sets_b = sum(1 for x, y in new_sets if y > x)
            if leader_name:
                body = f"{leader_name} takes set {closed_idx + 1} {a}-{b}. Sets: {sets_a}-{sets_b}."
            else:
                body = f"Set {closed_idx + 1} ends {a}-{b}."
            events.append(MatchEvent(
                match_id=match_id, kind="set_end", title="Set complete", body=body,
            ))

        # Tiebreak start: current set hits 6-6 for the first time. Compare
        # the current set in old vs new — if it just became 6-6, fire.
        if new_sets:
            cur_idx = len(new_sets) - 1
            cur = new_sets[cur_idx]
            old_cur = old_sets[cur_idx] if cur_idx < len(old_sets) else None
            if _at_tiebreak_score(cur) and old_cur != cur:
                events.append(MatchEvent(
                    match_id=match_id,
                    kind="tiebreak_start",
                    title="Tiebreak",
                    body=f"Set {cur_idx + 1} is going to a tiebreak (6-6).",
                ))

        # Game end + break-of-serve: total games delta of exactly 1.
        old_total_p1 = sum(a for a, _ in old_sets)
        old_total_p2 = sum(b for _, b in old_sets)
        new_total_p1 = sum(a for a, _ in new_sets)
        new_total_p2 = sum(b for _, b in new_sets)
        delta_p1 = new_total_p1 - old_total_p1
        delta_p2 = new_total_p2 - old_total_p2
        delta_total = delta_p1 + delta_p2

        if delta_total == 1 and old_server_id is not None:
            # Exactly one game elapsed — we can attribute it cleanly.
            cur = new_sets[-1] if new_sets else (0, 0)
            scoreline = f"{cur[0]}-{cur[1]}"
            sets_str = f"{new_total_p1}-{new_total_p2}"  # not quite but used only as flavor
            if delta_p1 == 1 and old_server_id == p2_id:
                events.append(MatchEvent(
                    match_id=match_id,
                    kind="break_of_serve",
                    title="Break!",
                    body=f"{p1_name} breaks {p2_name}. {scoreline} in current set.",
                ))
            elif delta_p2 == 1 and old_server_id == p1_id:
                events.append(MatchEvent(
                    match_id=match_id,
                    kind="break_of_serve",
                    title="Break!",
                    body=f"{p2_name} breaks {p1_name}. {scoreline} in current set.",
                ))
            else:
                # Hold of serve — surface as game_end (every_game subscribers only)
                holder = p1_name if delta_p1 == 1 else p2_name
                events.append(MatchEvent(
                    match_id=match_id,
                    kind="game_end",
                    title="Game",
                    body=f"{holder} holds. {scoreline} in current set.",
                ))
        elif delta_total > 1:
            # Multiple games elapsed since last poll — emit a generic update
            # for every_game subscribers without trying to attribute breaks.
            cur = new_sets[-1] if new_sets else (0, 0)
            events.append(MatchEvent(
                match_id=match_id,
                kind="game_end",
                title="Score update",
                body=f"{p1_name} {new_total_p1} – {new_total_p2} {p2_name} (current set {cur[0]}-{cur[1]}).",
            ))

    return events
