"""Persist provider data into our schema.

Keeps the provider contract narrow — providers only emit `LiveMatch`.
This layer handles upsert: tournaments, players, matches.
"""

import json
from datetime import datetime

from slugify import slugify

from app.services.tournament_resolver import canonical_slug
from sqlmodel import Session, select

from app.models.match import Match, MatchStatus
from app.models.player import Player, Tour
from app.models.tournament import Tournament, TournamentCategory
from app.services.categorize import categorize
from app.services.live.base import LiveMatch
from app.services.match_events import MatchEvent, detect_events
from app.services.match_stats import compute_stats
from app.services.player_dedup import find_player_by_name, name_key


def _upsert_player(session: Session, name: str, tour: Tour, country: str | None, external_id: str | None) -> Player:
    """Find or create a Player row.

    Three-stage lookup so we don't keep producing duplicates when the same
    person appears under slightly different names across data sources:
      1. external_id (api_tennis_id) — most reliable when present
      2. order-insensitive `name_key` — handles "Thiago Agustin Tirante" vs
         "Agustin Tirante Thiago" by sorting tokens before comparing
      3. (slug, tour) — tight match for the same exact serialization
    On miss we create with a tour-suffixed slug if the global slug already
    exists on a different tour (Player.slug is globally unique).
    """
    if external_id:
        existing_by_id = session.exec(
            select(Player).where(Player.api_tennis_id == external_id)
        ).first()
        if existing_by_id:
            if existing_by_id.name_key is None:
                existing_by_id.name_key = name_key(existing_by_id.full_name)
                session.add(existing_by_id)
            return existing_by_id

    by_name = find_player_by_name(session, name, tour)
    if by_name:
        if external_id and not by_name.api_tennis_id:
            by_name.api_tennis_id = external_id
            by_name.updated_at = datetime.utcnow()
            session.add(by_name)
        return by_name

    base_slug = slugify(name)[:80]

    # Existing player on the same tour with this slug → reuse.
    existing = session.exec(
        select(Player).where(Player.slug == base_slug, Player.tour == tour)
    ).first()
    if existing:
        if external_id and not existing.api_tennis_id:
            existing.api_tennis_id = external_id
            existing.updated_at = datetime.utcnow()
            session.add(existing)
        if existing.name_key is None:
            existing.name_key = name_key(existing.full_name)
            session.add(existing)
        return existing

    # Same slug on a different tour means cross-tour collision; disambiguate.
    cross = session.exec(select(Player).where(Player.slug == base_slug)).first()
    if cross is None:
        slug = base_slug
    else:
        slug = f"{base_slug}-{tour.value}"
        # If the suffixed slug already exists, look it up; if it's the wrong
        # tour we've got a degenerate three-way collision — counter-suffix.
        existing_suffixed = session.exec(select(Player).where(Player.slug == slug)).first()
        if existing_suffixed is not None and existing_suffixed.tour == tour:
            if external_id and not existing_suffixed.api_tennis_id:
                existing_suffixed.api_tennis_id = external_id
                existing_suffixed.updated_at = datetime.utcnow()
                session.add(existing_suffixed)
            return existing_suffixed
        n = 2
        while existing_suffixed is not None:
            slug = f"{base_slug}-{tour.value}-{n}"
            existing_suffixed = session.exec(select(Player).where(Player.slug == slug)).first()
            n += 1
            if n > 9:  # very unlikely; bail rather than loop forever
                break

    player = Player(
        slug=slug,
        full_name=name,
        tour=tour,
        country_code=country,
        api_tennis_id=external_id,
        name_key=name_key(name),
    )
    session.add(player)
    session.flush()
    return player


# Process-local cache of tournament ids keyed by (slug, tour, year). The
# live WS consumer fires a tournament lookup for every match update — with
# Rome ATP/WTA, Madrid, etc. simultaneously live, the same ~5 rows get
# selected hundreds of times a minute, each one fighting for the SQLite
# write lock when a backfill is needed. Cache means one lookup per
# tournament per process lifetime.
#
# (slug, tour, year) is immutable so we never need to invalidate. We cache
# the int id rather than the ORM object because ORM objects are
# session-bound.
_TOURNAMENT_ID_CACHE: dict[tuple[str, Tour, int], int] = {}


def _upsert_tournament(session: Session, name: str, tour: Tour, year: int, surface: str | None, external_id: str | None) -> int:
    slug = canonical_slug(name)
    key = (slug, tour, year)
    cached = _TOURNAMENT_ID_CACHE.get(key)
    if cached is not None:
        return cached

    stmt = select(Tournament).where(
        Tournament.slug == slug, Tournament.year == year, Tournament.tour == tour
    )
    t = session.exec(stmt).first()
    if t:
        if external_id and not t.api_tennis_id:
            t.api_tennis_id = external_id
            session.add(t)
        assert t.id is not None
        _TOURNAMENT_ID_CACHE[key] = t.id
        return t.id
    t = Tournament(
        slug=slug,
        year=year,
        name=name,
        tour=tour,
        category=categorize(name, tour),
        surface=surface,
        api_tennis_id=external_id,
    )
    session.add(t)
    session.flush()
    assert t.id is not None
    _TOURNAMENT_ID_CACHE[key] = t.id
    return t.id


# Round-name synonyms used by _find_orphan_wiki_row. Wikipedia rows are
# created with short codes (F, SF, QF, R16, ...) by app.services.
# wiki_brackets_apply; api-tennis pushes verbose strings like
# "ATP Rome - Final" / "1/8-final". Map one form to the other so the
# orphan lookup can stitch a Wikipedia row to its live-update partner.
_ROUND_SYNONYMS: dict[str, tuple[str, ...]] = {
    "f": ("final", " - final"),
    "sf": ("semi-final", "semifinal"),
    "qf": ("quarter-final", "quarterfinal"),
    "r16": ("1/8-final", "fourth round"),
    "r32": ("1/16-final", "third round"),
    "r64": ("1/32-final", "second round"),
    "r128": ("1/64-final", "first round"),
}


def _rounds_match(short_or_verbose: str, other: str) -> bool:
    """Compare two round labels case-insensitively, treating either form
    (short like 'F', verbose like 'ATP Rome - Final') as equivalent."""
    a = short_or_verbose.lower().strip()
    b = other.lower().strip()
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True
    # Try short → verbose
    for short, verboses in _ROUND_SYNONYMS.items():
        if (a == short and any(v in b for v in verboses)) or (
            b == short and any(v in a for v in verboses)
        ):
            return True
    return False


def _find_orphan_wiki_row(
    session: Session,
    *,
    tournament_id: int,
    p1_id: int,
    p2_id: int,
    round_label: str,
    is_doubles: bool,
) -> Match | None:
    """Look for a Match row that was created by the Wikipedia pipeline
    (api_tennis_id IS NULL) and matches the same (tournament, player pair,
    round) the api-tennis push is for. Used to adopt orphan Wikipedia rows
    on first api-tennis sight, so we don't end up with two rows per
    real-world match."""
    candidates = session.exec(
        select(Match).where(
            Match.tournament_id == tournament_id,
            Match.api_tennis_id.is_(None),
            Match.is_doubles == is_doubles,
        )
    ).all()
    target = {p1_id, p2_id}
    for m in candidates:
        pair = {m.player1_id, m.player2_id}
        if pair != target:
            continue
        if _rounds_match(m.round or "", round_label):
            return m
    return None


def upsert_live_matches(
    session: Session, live_matches: list[LiveMatch]
) -> tuple[int, list[MatchEvent]]:
    """Upsert provider data. Returns (rows touched, events to emit).

    Events are computed by diffing each existing match's prior state against
    the incoming payload. Brand-new matches don't generate events except a
    `match_start` if their initial status is already live.
    """
    touched = 0
    events: list[MatchEvent] = []
    for lm in live_matches:
        tour = Tour(lm.tour)
        year = (lm.scheduled_at or datetime.utcnow()).year

        tournament_id = _upsert_tournament(
            session, lm.tournament_name, tour, year, lm.surface, lm.tournament_external_id
        )

        p1 = _upsert_player(session, lm.player1_name, tour, lm.player1_country, lm.player1_external_id) if lm.player1_name else None
        p2 = _upsert_player(session, lm.player2_name, tour, lm.player2_country, lm.player2_external_id) if lm.player2_name else None

        stmt = select(Match).where(Match.api_tennis_id == lm.provider_match_id)
        match = session.exec(stmt).first()

        # Fallback: row created earlier by the Wikipedia bracket pipeline
        # has api_tennis_id=NULL but matches the same (tournament, player
        # pair, round) — adopt it instead of creating a duplicate. After
        # adoption, attach api_tennis_id so all subsequent live updates
        # find it via the fast path above.
        if match is None and p1 is not None and p2 is not None:
            match = _find_orphan_wiki_row(
                session,
                tournament_id=tournament_id,
                p1_id=p1.id,
                p2_id=p2.id,
                round_label=lm.round or "",
                is_doubles=lm.is_doubles,
            )
            if match is not None:
                match.api_tennis_id = lm.provider_match_id

        winner_id = None
        if lm.winner == 1 and p1:
            winner_id = p1.id
        elif lm.winner == 2 and p2:
            winner_id = p2.id

        if match:
            old_status = match.status.value if match.status else "scheduled"
            old_score = match.score
            old_server = match.server_player_id

            match.status = MatchStatus(lm.status)
            match.score = lm.score
            match.current_set = lm.current_set
            match.current_game = lm.current_game
            match.server_player_id = (p1.id if lm.server == 1 else p2.id if lm.server == 2 else None)
            match.winner_id = winner_id
            # Refresh scheduled_at on every upsert. Without this, fixes
            # like the api-tennis timezone=UTC param never propagate to
            # rows that already exist — they'd stay at the wrong time
            # forever. Also handles rescheduled matches.
            if lm.scheduled_at is not None:
                match.scheduled_at = lm.scheduled_at
            match.updated_at = datetime.utcnow()
            if lm.status == "finished" and not match.finished_at:
                match.finished_at = datetime.utcnow()
            stats = compute_stats(lm.raw.get("pointbypoint") if lm.raw else None)
            if stats is not None:
                match.stats_json = json.dumps(stats)
            session.add(match)

            if p1 and p2 and match.id is not None:
                events.extend(
                    detect_events(
                        match_id=match.id,
                        old_status=old_status,
                        old_score=old_score,
                        old_server_id=old_server,
                        new_status=lm.status,
                        new_score=lm.score,
                        p1_id=p1.id,
                        p2_id=p2.id,
                        p1_name=p1.full_name,
                        p2_name=p2.full_name,
                    )
                )
        else:
            stats = compute_stats(lm.raw.get("pointbypoint") if lm.raw else None)
            match = Match(
                tournament_id=tournament_id,
                round=lm.round,
                scheduled_at=lm.scheduled_at,
                started_at=lm.started_at,
                finished_at=lm.finished_at,
                status=MatchStatus(lm.status),
                player1_id=p1.id if p1 else None,
                player2_id=p2.id if p2 else None,
                score=lm.score,
                current_set=lm.current_set,
                current_game=lm.current_game,
                server_player_id=(p1.id if lm.server == 1 else p2.id if lm.server == 2 else None),
                winner_id=winner_id,
                is_doubles=lm.is_doubles,
                best_of=lm.best_of,
                api_tennis_id=lm.provider_match_id,
                stats_json=json.dumps(stats) if stats is not None else None,
            )
            session.add(match)
        touched += 1

        # Commit after every match so we don't hold the SQLite writer lock
        # for an entire batch (was up to 50+ matches under a single
        # transaction, blocking every other writer for seconds at a time).
        session.commit()
    return touched, events
