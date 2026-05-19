"""Templated match blurb generator.

Produces a paragraph-grade preview (for scheduled matches) or recap
(for finished/retired/walkover matches) using a small pool of
sentence templates. No LLM in the loop — every sentence is composed
from real match + H2H data and rotated through the pool deterministically
by match.id, so:

  - The same match always reads the same way on every page load
    (caching-friendly, no flicker on revalidate).
  - Two adjacent matches with similar shapes don't read identical
    because they pick different template variants.

Each section of the paragraph (opening / form / H2H / closer) has
its own pool. The blurb is short on purpose — 2-4 sentences feels
human; 6+ feels like padding.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlmodel import Session, select

from app.models.match import Match, MatchStatus
from app.models.player import Player
from app.models.tournament import Tournament


@dataclass
class H2HContext:
    """The slice of H2H we use for blurb composition. Populated by the
    caller from the same data the H2H endpoint computes."""
    total_meetings: int
    p1_wins: int                  # wins for match.player1
    p2_wins: int                  # wins for match.player2
    finals_meetings: int
    current_streak_slug: str | None
    current_streak_count: int
    first_meeting_year: int | None


# Statuses that count as a completed meeting for H2H purposes.
# RETIRED + WALKOVER attribute a winner, so they belong in the rivalry
# tally. (The /api/h2h endpoint currently filters FINISHED-only — that's
# a pre-existing inconsistency we'll leave alone.)
_COMPLETE_STATUSES = (
    MatchStatus.FINISHED,
    MatchStatus.RETIRED,
    MatchStatus.WALKOVER,
)


def compute_h2h_context(
    session: Session, match: Match, p1: Player, p2: Player,
) -> H2HContext:
    """Lean H2H computation for blurb generation.

    Walks all completed meetings between p1 and p2 in one query and
    derives the small set of numbers the templates actually consume.
    The current match is included when it has already been completed
    (so a recap can correctly say 'now leads X-Y').
    """
    stmt = (
        select(Match)
        .where(
            ((Match.player1_id == p1.id) & (Match.player2_id == p2.id))
            | ((Match.player1_id == p2.id) & (Match.player2_id == p1.id)),
            Match.status.in_(_COMPLETE_STATUSES),
        )
        .order_by(Match.scheduled_at.desc())
    )
    matches = session.exec(stmt).all()
    if not matches:
        return H2HContext(0, 0, 0, 0, None, 0, None)

    p1_wins = sum(1 for m in matches if m.winner_id == p1.id)
    p2_wins = sum(1 for m in matches if m.winner_id == p2.id)

    finals = sum(
        1 for m in matches
        if (m.round or "").lower().strip().rstrip("s").endswith("final")
        or (m.round or "").strip().upper() == "F"
    )

    streak_id: int | None = None
    streak_count = 0
    for m in matches:
        if m.winner_id is None:
            break
        if streak_id is None:
            streak_id = m.winner_id
            streak_count = 1
        elif m.winner_id == streak_id:
            streak_count += 1
        else:
            break
    streak_slug: str | None = (
        p1.slug if streak_id == p1.id
        else p2.slug if streak_id == p2.id
        else None
    )

    first_year: int | None = None
    for m in reversed(matches):
        if m.scheduled_at is not None:
            first_year = m.scheduled_at.year
            break

    return H2HContext(
        total_meetings=len(matches),
        p1_wins=p1_wins,
        p2_wins=p2_wins,
        finals_meetings=finals,
        current_streak_slug=streak_slug,
        current_streak_count=streak_count,
        first_meeting_year=first_year,
    )


def _pick(pool: list[str], seed: int) -> str:
    """Stable choice from a non-empty pool based on `seed % len(pool)`."""
    if not pool:
        return ""
    return pool[seed % len(pool)]


def _name(p: Player | None) -> str:
    return p.full_name if p else "TBD"


def _last_name(p: Player | None) -> str:
    """Best-effort last name for second-mention variation. Falls back to
    full name if we can't split cleanly."""
    if not p or not p.full_name:
        return "TBD"
    # Handle "van de Zandschulp", "Davidovich Fokina" — take last two
    # tokens if first looks like a particle.
    parts = p.full_name.strip().split()
    if not parts:
        return p.full_name
    return parts[-1]


def _round_label(round_str: str | None) -> str:
    if not round_str:
        return ""
    s = round_str.strip().lower()
    # Short codes from Wikipedia pipeline.
    mapping = {
        "f": "final", "sf": "semi-final", "qf": "quarter-final",
        "r16": "round of 16", "r32": "third round",
        "r64": "second round", "r128": "first round",
    }
    if s in mapping:
        return mapping[s]
    # api-tennis verbose: "ATP Rome - Quarter-finals" → "quarter-final"
    if "final" in s:
        if "semi" in s:
            return "semi-final"
        if "quarter" in s:
            return "quarter-final"
        if s.rstrip("s").endswith("final"):
            return "final"
    if "1/8" in s:
        return "round of 16"
    if "1/16" in s:
        return "third round"
    if "1/32" in s:
        return "second round"
    if "1/64" in s:
        return "first round"
    return round_str


def _score_summary(score: str | None) -> str:
    """Short summary of how the win went. Returns a fragment fit for
    inclusion in a sentence (e.g., 'in straight sets', 'in three',
    'in a tight three-setter')."""
    if not score:
        return ""
    sets = score.split()
    if len(sets) <= 1:
        return ""
    if len(sets) == 2:
        return "in straight sets"
    if len(sets) == 3:
        return "in three"
    if len(sets) == 4:
        return "in four"
    if len(sets) == 5:
        return "in five"
    return ""


def build_blurb(
    match: Match,
    player1: Player | None,
    player2: Player | None,
    tournament: Tournament | None,
    h2h: H2HContext | None,
) -> tuple[str, str]:
    """Return (kind, paragraph). kind is one of 'preview' / 'recap' /
    '' (empty for live matches). Empty kind ⇒ caller should suppress
    the blurb section entirely."""
    if not match or not player1 or not player2 or not tournament:
        return "", ""

    # Skip live + suspended — the live scorecard is the page's draw.
    if match.status in (MatchStatus.LIVE, MatchStatus.SUSPENDED):
        return "", ""

    seed = match.id or 0
    finished = match.status in (
        MatchStatus.FINISHED, MatchStatus.RETIRED, MatchStatus.WALKOVER,
    )
    if finished:
        para = _recap(match, player1, player2, tournament, h2h, seed)
        return ("recap", para)
    if match.status == MatchStatus.SCHEDULED:
        para = _preview(match, player1, player2, tournament, h2h, seed)
        return ("preview", para)
    return "", ""


# ---------------------------------------------------------------------------
# Recap composition
# ---------------------------------------------------------------------------


_RECAP_OPENINGS = [
    "{Winner} defeated {Loser} {score_str}{score_summary} in the {round} of the {year} {tournament}.",
    "{Winner} got past {Loser} {score_str}{score_summary} to win their {round} match at the {year} {tournament}.",
    "{Winner} saw off {Loser} {score_str}{score_summary} in the {round} at the {year} {tournament}.",
    "It was {Winner} over {Loser} {score_str}{score_summary} in the {round} of the {year} {tournament}.",
]

_RECAP_OPENINGS_RETIRED = [
    "{Winner} advanced past {Loser} {score_str} when his opponent retired in the {round} of the {year} {tournament}.",
    "{Loser} retired in the {round} against {Winner} at the {year} {tournament}, with the score at {score_str}.",
]

_RECAP_OPENINGS_WALKOVER = [
    "{Winner} advanced to the next round by walkover after {Loser} withdrew before their {round} match at the {year} {tournament}.",
]

# Sentences sentences for the H2H beat. Each slot expects {WinnerLast},
# {LoserLast}, and the H2H counts pre-filled.
_RECAP_H2H_FRESH = [
    "It was their first meeting.",
    "The two had never met before on tour.",
]

_RECAP_H2H_LEADS = [
    "The win moves {WinnerLast} to {win_count}–{loss_count} in the head-to-head.",
    "{WinnerLast} now leads the rivalry {win_count}–{loss_count}.",
    "It was their {n}{ordinal} career meeting; {WinnerLast} now leads {win_count}–{loss_count}.",
]

_RECAP_H2H_TRAILS = [
    "{WinnerLast} closes the gap to {win_count}–{loss_count} in their head-to-head with {LoserLast}.",
    "Despite the win, {LoserLast} still leads the rivalry {loss_count}–{win_count}.",
]

_RECAP_H2H_LEVEL = [
    "It was their {n}{ordinal} meeting; the rivalry now stands level at {win_count}–{loss_count}.",
    "The rivalry is locked at {win_count}–{loss_count} after their {n}{ordinal} meeting.",
]


def _recap(
    match: Match,
    p1: Player, p2: Player,
    t: Tournament,
    h2h: H2HContext | None,
    seed: int,
) -> str:
    # Winner / loser orientation.
    winner = p1 if match.winner_id == p1.id else p2 if match.winner_id == p2.id else None
    loser = p2 if winner is p1 else p1 if winner is p2 else None
    if winner is None or loser is None:
        # Result not known (shouldn't happen for FINISHED, but defensive).
        return ""

    score_str = match.score or ""
    score_summary = _score_summary(match.score)
    suffix = (" " + score_summary) if score_summary else ""

    if match.status == MatchStatus.RETIRED:
        opening_pool = _RECAP_OPENINGS_RETIRED
    elif match.status == MatchStatus.WALKOVER:
        opening_pool = _RECAP_OPENINGS_WALKOVER
    else:
        opening_pool = _RECAP_OPENINGS

    opening = _pick(opening_pool, seed).format(
        Winner=_name(winner),
        Loser=_name(loser),
        score_str=score_str or "the match",
        score_summary=suffix,
        round=_round_label(match.round) or "",
        year=t.year,
        tournament=t.name,
    )

    # H2H beat. Only meaningful when we have h2h context — and even then
    # only when there are >= 2 meetings worth talking about.
    h2h_sentence = _h2h_recap_sentence(winner, loser, h2h, p1, p2, seed)

    pieces = [opening]
    if h2h_sentence:
        pieces.append(h2h_sentence)
    return " ".join(pieces)


def _h2h_recap_sentence(
    winner: Player, loser: Player,
    h2h: H2HContext | None,
    p1: Player, p2: Player,
    seed: int,
) -> str:
    if h2h is None or h2h.total_meetings < 1:
        return ""

    # Map winner-vs-loser to the win/loss counts on the right orientation.
    if winner.id == p1.id:
        winner_wins, loser_wins = h2h.p1_wins, h2h.p2_wins
    else:
        winner_wins, loser_wins = h2h.p2_wins, h2h.p1_wins

    if h2h.total_meetings == 1:
        return _pick(_RECAP_H2H_FRESH, seed)

    if winner_wins == loser_wins:
        return _pick(_RECAP_H2H_LEVEL, seed).format(
            WinnerLast=_last_name(winner),
            LoserLast=_last_name(loser),
            n=h2h.total_meetings,
            ordinal=_ordinal_suffix(h2h.total_meetings),
            win_count=winner_wins, loss_count=loser_wins,
        )
    if winner_wins > loser_wins:
        return _pick(_RECAP_H2H_LEADS, seed).format(
            WinnerLast=_last_name(winner),
            LoserLast=_last_name(loser),
            win_count=winner_wins, loss_count=loser_wins,
            n=h2h.total_meetings,
            ordinal=_ordinal_suffix(h2h.total_meetings),
        )
    return _pick(_RECAP_H2H_TRAILS, seed).format(
        WinnerLast=_last_name(winner),
        LoserLast=_last_name(loser),
        win_count=winner_wins, loss_count=loser_wins,
    )


def _ordinal_suffix(n: int) -> str:
    # 1st 2nd 3rd 4th 11th 12th 13th 21st …
    if 10 <= (n % 100) <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


# ---------------------------------------------------------------------------
# Preview composition
# ---------------------------------------------------------------------------


_PREVIEW_OPENINGS = [
    "{P1} faces {P2} in the {round} of the {year} {tournament}.",
    "{P1} meets {P2} in their {round} match at the {year} {tournament}.",
    "Up next at the {year} {tournament}: {P1} against {P2} in the {round}.",
    "{P1} and {P2} clash in the {round} at the {year} {tournament}.",
]

_PREVIEW_NEW_RIVALRY = [
    "It will be the first time they've met on tour.",
    "The pair have never faced each other before.",
]

_PREVIEW_RIVALRY_LEADS_P1 = [
    "{P1Last} leads their head-to-head {p1_wins}–{p2_wins} from {meetings} previous meetings.",
    "They've met {meetings} times before, with {P1Last} winning {p1_wins}.",
]

_PREVIEW_RIVALRY_LEADS_P2 = [
    "{P2Last} leads their head-to-head {p2_wins}–{p1_wins} from {meetings} previous meetings.",
    "They've met {meetings} times before, with {P2Last} winning {p2_wins}.",
]

_PREVIEW_RIVALRY_LEVEL = [
    "Their head-to-head is level at {p1_wins}–{p2_wins} from {meetings} meetings.",
    "The rivalry is locked at {p1_wins}–{p2_wins} going into this one.",
]

_PREVIEW_STREAK = [
    "{StreakLast} has won the last {streak_count} meetings between them.",
    "{StreakLast} has been the winner in each of their last {streak_count} encounters.",
]

_PREVIEW_FINALS_FREQ = [
    "{finals} of their previous meetings have come in a final.",
    "They've met in {finals} finals before this one.",
]


def _preview(
    match: Match,
    p1: Player, p2: Player,
    t: Tournament,
    h2h: H2HContext | None,
    seed: int,
) -> str:
    opening = _pick(_PREVIEW_OPENINGS, seed).format(
        P1=_name(p1), P2=_name(p2),
        round=_round_label(match.round) or "next round",
        year=t.year, tournament=t.name,
    )

    pieces = [opening]
    h2h_sentence = _h2h_preview_sentence(p1, p2, h2h, seed)
    if h2h_sentence:
        pieces.append(h2h_sentence)
    streak_sentence = _streak_sentence(p1, p2, h2h, seed)
    if streak_sentence:
        pieces.append(streak_sentence)
    finals_sentence = _finals_freq_sentence(h2h, seed)
    if finals_sentence:
        pieces.append(finals_sentence)
    return " ".join(pieces)


def _h2h_preview_sentence(
    p1: Player, p2: Player,
    h2h: H2HContext | None,
    seed: int,
) -> str:
    if h2h is None or h2h.total_meetings == 0:
        return _pick(_PREVIEW_NEW_RIVALRY, seed)
    if h2h.p1_wins == h2h.p2_wins:
        return _pick(_PREVIEW_RIVALRY_LEVEL, seed).format(
            p1_wins=h2h.p1_wins, p2_wins=h2h.p2_wins,
            meetings=h2h.total_meetings,
        )
    pool = _PREVIEW_RIVALRY_LEADS_P1 if h2h.p1_wins > h2h.p2_wins else _PREVIEW_RIVALRY_LEADS_P2
    return _pick(pool, seed).format(
        P1Last=_last_name(p1), P2Last=_last_name(p2),
        p1_wins=h2h.p1_wins, p2_wins=h2h.p2_wins,
        meetings=h2h.total_meetings,
    )


def _streak_sentence(
    p1: Player, p2: Player,
    h2h: H2HContext | None,
    seed: int,
) -> str:
    if h2h is None or not h2h.current_streak_slug or h2h.current_streak_count < 2:
        return ""
    if h2h.current_streak_slug == p1.slug:
        streaker = p1
    elif h2h.current_streak_slug == p2.slug:
        streaker = p2
    else:
        return ""
    return _pick(_PREVIEW_STREAK, seed).format(
        StreakLast=_last_name(streaker),
        streak_count=h2h.current_streak_count,
    )


def _finals_freq_sentence(h2h: H2HContext | None, seed: int) -> str:
    if h2h is None or h2h.finals_meetings < 2:
        return ""
    return _pick(_PREVIEW_FINALS_FREQ, seed).format(finals=h2h.finals_meetings)
