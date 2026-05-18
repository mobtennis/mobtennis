"""Reconcile a ParsedBracket (from wiki_brackets.py) with our DB.

Phase 2 of the new pipeline. The parser is pure; this module is where DB
mutations happen. Kept deliberately small — each step is named so the CLI
can dry-run and report.

Resolution policy:
  - team.wikilink (Wikipedia canonical title) → slug via slugify(),
    minus disambiguators like "(tennis)" / "(Brazilian)".
  - Failing that, look up our static overrides table in
    wiki_brackets_overrides.py.
  - Failing both, log as unresolved. The CLI prints unresolved players
    at the end so we can grow the overrides table over time.

Write policy (per match):
  - bracket_position, player1_seed, player2_seed   → always overwrite
  - score, winner_id, status                       → overwrite from
    Wikipedia for any match Wikipedia considers played (it has scores)
  - api-tennis-specific data (api_tennis_id, stats_json, current_set
    / current_game) is not touched

If a Match row doesn't exist in our DB yet, we create one. The api-tennis
live consumer attaches its own api_tennis_id on first sight, so future
live updates flow into our row regardless of who created it.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime

from sqlmodel import Session, select

from app.models.match import Match, MatchStatus
from app.models.player import Player, Tour
from app.models.tournament import Tournament
from app.services.wiki_brackets import ParsedBracket, WikiMatch, WikiPlayer
from app.services.wiki_brackets_overrides import WIKI_TITLE_TO_SLUG

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Player resolution
# ---------------------------------------------------------------------------


_DISAMBIG_RE = re.compile(r"\s*\([^)]+\)\s*$")


def _ascii_lower_clean(s: str) -> str:
    """Drop diacritics, lowercase, no other transforms."""
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def _slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _ascii_lower_clean(s)).strip("-")


def _wikilink_to_slug(wikilink: str) -> str:
    """Convert a Wikipedia canonical title to our slug shape:
      "Sebastian Ofner"            → "sebastian-ofner"
      "Alexander Shevchenko (tennis)" → "alexander-shevchenko"
      "Martín Landaluce"           → "martin-landaluce"
    """
    s = _DISAMBIG_RE.sub("", wikilink).strip()
    return _slugify(s)


def _candidate_slugs(wikilink: str) -> list[str]:
    """Return all the slug shapes we'll try, in priority order. Same input
    might appear in our DB under different conventions:

      Sackmann shape ("full"):    "roberto-bautista-agut"
      api-tennis shape (abbrev):  "h-hurkacz", "a-mannarino"

    Wikipedia always gives us the full canonical name, so we generate
    both shapes from it and try each.

    For multi-word names there's also disagreement about how many
    given-name initials to include:

      "Juan Manuel Cerúndolo"  → "j-m-cerundolo"  (initials of all
                                                    pre-surname tokens)
                              OR "j-cerundolo"    (single initial)

    We try the full form, then progressively more abbreviated forms.
    """
    bare = _DISAMBIG_RE.sub("", wikilink).strip()
    if not bare:
        return []
    tokens = bare.split()
    if not tokens:
        return []

    candidates: list[str] = []
    seen: set[str] = set()

    def push(parts: list[str]) -> None:
        if not parts:
            return
        slug = _slugify(" ".join(parts))
        if slug and slug not in seen:
            seen.add(slug)
            candidates.append(slug)

    # 1. Full canonical: "Juan Manuel Cerundolo" → "juan-manuel-cerundolo"
    push(tokens)
    # 2. Single first initial + last token: "j-cerundolo"
    if len(tokens) >= 2:
        push([tokens[0][:1], tokens[-1]])
    # 3. Initials of every pre-last token + last token:
    #    "Juan Manuel Cerúndolo" → "j-m-cerundolo"
    if len(tokens) >= 3:
        push([*[t[:1] for t in tokens[:-1]], tokens[-1]])
    # 4. Some last names span multiple tokens ("van de Zandschulp",
    #    "Bautista Agut", "Davidovich Fokina"). api-tennis often keeps
    #    them together, so also try first-initial + everything-after-
    #    the-given-name as a multi-token last name.
    if len(tokens) >= 3:
        push([tokens[0][:1], *tokens[1:]])
    # 5. East Asian name order — Wikipedia preserves "family-name first"
    #    (e.g., "Zhang Zhizhen"), but downstream sources interpret the
    #    first token as the given name and reverse the order. Two
    #    common slug shapes result:
    #       full reversed:    "Shuai Zhang"   → "shuai-zhang"   (Sackmann)
    #       initial reversed: "Z. Zhang"      → "z-zhang"       (api-tennis)
    #    Try both for two-token names.
    if len(tokens) == 2:
        push([tokens[-1], tokens[0]])            # full reversed
        push([tokens[-1][:1], tokens[0]])        # initial reversed
    return candidates


@dataclass
class ResolutionResult:
    player: Player | None
    slug_tried: str
    resolved_via: str | None  # "slug" | "overrides" | None


def resolve_player(session: Session, wikilink: str, tour: Tour) -> ResolutionResult:
    """Look up a Wikipedia-named player in our Player table.

    Resolution order, in order of confidence:
      1. Static overrides table (exact Wikipedia-title match)
      2. Each candidate slug from _candidate_slugs() — these cover
         both Sackmann (full) and api-tennis (abbreviated) shapes
    Tour-scoped to avoid the rare cross-tour name collision.
    """
    # Overrides win, so a known-tricky title doesn't accidentally match
    # the wrong player via a generic slug strategy.
    override_slug = WIKI_TITLE_TO_SLUG.get(wikilink)
    if override_slug:
        p = session.exec(
            select(Player).where(Player.slug == override_slug, Player.tour == tour)
        ).first()
        if p is not None:
            return ResolutionResult(p, override_slug, "overrides")

    candidates = _candidate_slugs(wikilink)
    for slug in candidates:
        p = session.exec(
            select(Player).where(Player.slug == slug, Player.tour == tour)
        ).first()
        if p is not None:
            return ResolutionResult(p, slug, "slug")

    # Returned slug_tried is the first candidate (the full form) — that's
    # the one users will recognise when looking at the unresolved list.
    return ResolutionResult(None, candidates[0] if candidates else "", None)


# ---------------------------------------------------------------------------
# Score / status derivation
# ---------------------------------------------------------------------------


def _detect_status(score: str | None, winner_present: bool) -> MatchStatus:
    """Map a Wikipedia row to a MatchStatus.

    Wikipedia doesn't surface 'live' or 'suspended' — its scores are
    only the final result. So everything we parse from there is either
    FINISHED or hasn't happened yet (no score, no winner).
    """
    if not score:
        return MatchStatus.SCHEDULED
    if "(r)" in score.lower() or "ret" in score.lower():
        return MatchStatus.RETIRED
    if "w/o" in score.lower() or "walkover" in score.lower():
        return MatchStatus.WALKOVER
    return MatchStatus.FINISHED if winner_present else MatchStatus.SCHEDULED


def _seed_to_int(seed: str | None) -> int | None:
    """Coerce a parsed seed string to int. Non-numeric tokens (Q, WC,
    LL, PR, etc.) come back as None — those aren't 'seeds' in the
    numeric sense, they're entry routes."""
    if not seed:
        return None
    try:
        return int(seed)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Match reconciliation
# ---------------------------------------------------------------------------


@dataclass
class ApplyResult:
    tournament_id: int
    page_title: str
    nuked_existing: int = 0
    created: int = 0
    updated: int = 0
    skipped_bye: int = 0
    unresolved: list[tuple[str, str]] = field(default_factory=list)  # (wikilink, slug_tried)
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"{self.page_title}: created={self.created} updated={self.updated} "
            f"skipped_byes={self.skipped_bye} "
            f"unresolved_players={len(self.unresolved)} "
            f"nuked_existing={self.nuked_existing}"
        )


def _round_to_db_label(round_name: str) -> str:
    """Map our internal round name to the label we store in Match.round.
    Keep it simple: store the same short label parser produces."""
    return round_name


def _find_existing_match(
    session: Session,
    *,
    tournament_id: int,
    p1_id: int,
    p2_id: int,
    round_label: str,
) -> Match | None:
    """Locate the Match row corresponding to a parsed WikiMatch.

    Match by player pair (order-insensitive) + round string match
    (substring, so 'F' matches '...Final' too). Same logic as the
    Sackmann ingest's _find_existing_match.
    """
    stmt = select(Match).where(
        Match.tournament_id == tournament_id,
        Match.is_doubles == False,  # noqa: E712
    )
    target = {p1_id, p2_id}
    round_lower = round_label.lower()
    for m in session.exec(stmt).all():
        pair = {m.player1_id, m.player2_id}
        if pair != target:
            continue
        mr = (m.round or "").lower()
        if round_lower in mr or mr in round_lower:
            return m
        # api-tennis spells rounds as "ATP Rome - Quarter-finals"; our
        # parser emits "QF". Map a couple of common synonyms.
        SYNONYMS = {
            "qf": "quarter-final",
            "sf": "semi-final",
            "f": "final",
            "r16": "1/8-final",
            "r32": "1/16-final",
            "r64": "1/32-final",
            "r128": "1/64-final",
        }
        syn = SYNONYMS.get(round_lower)
        if syn and syn in mr:
            return m
    return None


def apply_parsed_bracket(
    session: Session,
    tournament: Tournament,
    parsed: ParsedBracket,
    *,
    nuke_first: bool = False,
) -> ApplyResult:
    """Reconcile a ParsedBracket against the Match table for one tournament.

    If `nuke_first` is True, every singles Match row for the tournament is
    deleted before applying. Use when the existing data is known-broken
    and we want a clean rebuild.
    """
    tour = tournament.tour
    result = ApplyResult(tournament_id=tournament.id or 0, page_title=parsed.page_title)

    if nuke_first:
        # Only nuke non-Sackmann rows. Sackmann-sourced matches
        # (`sackmann_id IS NOT NULL`) are point #2 from the user's
        # tournament-page audit — "less of an issue, leave for now".
        # Wikipedia-driven rebuild is for live + recent events that
        # came through api-tennis.
        existing = session.exec(
            select(Match).where(
                Match.tournament_id == tournament.id,
                Match.is_doubles == False,  # noqa: E712
                Match.sackmann_id.is_(None),
            )
        ).all()
        for m in existing:
            session.delete(m)
        result.nuked_existing = len(existing)
        session.flush()

    for wm in parsed.matches:
        if wm.is_bye:
            result.skipped_bye += 1
            continue

        p1, p2 = None, None
        if wm.team1 and wm.team1.wikilink:
            r1 = resolve_player(session, wm.team1.wikilink, tour)
            p1 = r1.player
            if p1 is None:
                result.unresolved.append((wm.team1.wikilink, r1.slug_tried))
        if wm.team2 and wm.team2.wikilink:
            r2 = resolve_player(session, wm.team2.wikilink, tour)
            p2 = r2.player
            if p2 is None:
                result.unresolved.append((wm.team2.wikilink, r2.slug_tried))

        # If we couldn't resolve both players, we can't write a Match row.
        # Skip and let the user grow the overrides table; the parser run
        # logs all such cases.
        if p1 is None or p2 is None:
            continue

        winner_id = None
        if wm.team1 and wm.team1.won:
            winner_id = p1.id
        elif wm.team2 and wm.team2.won:
            winner_id = p2.id

        round_label = _round_to_db_label(wm.round_name)
        status = _detect_status(wm.score, winner_id is not None)

        seed1 = _seed_to_int(wm.team1.seed if wm.team1 else None)
        seed2 = _seed_to_int(wm.team2.seed if wm.team2 else None)

        existing = _find_existing_match(
            session,
            tournament_id=tournament.id,
            p1_id=p1.id,
            p2_id=p2.id,
            round_label=round_label,
        )

        if existing is not None:
            # Update in place. Don't touch api-tennis-specific fields.
            existing.bracket_position = wm.bracket_position
            # Preserve player1/2 orientation. If the existing row has
            # players the other way around, seeds need to swap.
            if existing.player1_id == p1.id:
                existing.player1_seed = seed1
                existing.player2_seed = seed2
            else:
                existing.player1_seed = seed2
                existing.player2_seed = seed1
            if wm.score:
                existing.score = wm.score
            if winner_id is not None:
                existing.winner_id = winner_id
            # Only "lift" the status. Don't downgrade a LIVE row to
            # SCHEDULED because Wikipedia hasn't propagated a score yet.
            if status == MatchStatus.FINISHED and existing.status != MatchStatus.FINISHED:
                existing.status = status
                if existing.finished_at is None:
                    existing.finished_at = datetime.utcnow()
            elif status in (MatchStatus.RETIRED, MatchStatus.WALKOVER):
                existing.status = status
            session.add(existing)
            result.updated += 1
        else:
            m = Match(
                tournament_id=tournament.id,
                round=round_label,
                status=status,
                is_doubles=False,
                player1_id=p1.id,
                player2_id=p2.id,
                player1_seed=seed1,
                player2_seed=seed2,
                score=wm.score,
                winner_id=winner_id,
                bracket_position=wm.bracket_position,
                finished_at=datetime.utcnow() if status == MatchStatus.FINISHED else None,
            )
            session.add(m)
            result.created += 1

    return result
