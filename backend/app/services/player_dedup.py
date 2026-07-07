"""Player deduplication helpers.

Tennis name data is gnarly. Sackmann ships canonical "Thiago Agustin
Tirante" first, and api-tennis ships "T. Agustin Tirante" or "Tirante
Thiago" depending on context. Slugifying each gives a different slug,
so we end up with several Player rows for the same human.

Two passes:

1. `name_key` (sorted-token lowercase form) — handles word-order swaps
   like "Thiago Agustin Tirante" vs "Agustin Tirante Thiago". Stored
   on the row, indexed, used by upsert paths.

2. Initial-form fuzzy match — handles "A. Tabilo" vs "Alejandro Tabilo".
   Same token count, all tokens equal except one pair where one is a
   single letter that prefixes the other. Run as a second-pass cleanup;
   not in upsert hot paths because it'd false-positive on first-name
   collisions ("A. Smith" matches "Alex Smith" but also "Andrew Smith").
   We pick the more-canonical row (api_tennis_id wins, then more
   matches, then lowest id) and merge.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from slugify import slugify
from sqlmodel import Session, select

from app.models.match import Match
from app.models.player import Player, Tour
from app.models.ranking import Ranking

log = logging.getLogger(__name__)


def name_key(name: str | None) -> str | None:
    """Sorted-token lowercase form of a player name.

    "Thiago Agustin Tirante" → "agustin-thiago-tirante"
    "Agustin Tirante, Thiago" → "agustin-thiago-tirante"
    "T. Tirante" → "t-tirante"  (initials still slug, can't undo them)

    Returns None when the slugified name is empty (e.g. all punctuation).
    """
    if not name:
        return None
    base = slugify(name)
    if not base:
        return None
    tokens = sorted(t for t in base.split("-") if t)
    return "-".join(tokens) or None


def find_player_by_name(
    session: Session, name: str, tour: Tour
) -> Player | None:
    """Look up a player by order-insensitive name + tour. Use this in
    upsert paths instead of (slug, tour) so you don't create a duplicate
    when a different source serializes the name differently."""
    key = name_key(name)
    if key is None:
        return None
    return session.exec(
        select(Player).where(Player.name_key == key, Player.tour == tour)
    ).first()


def merge_duplicates(session: Session) -> int:
    """One-shot cleanup: find players with matching name_key + tour, pick
    one canonical row, repoint all foreign keys to it, delete the rest.

    Returns count of rows merged away. Idempotent — running on a clean
    DB is a no-op.

    Strategy for "canonical":
      1. Has api_tennis_id (most reliable cross-source identifier)
      2. Has the most matches referencing it (most data attached)
      3. Lowest id (oldest row, most likely to be the correct one)
    """
    # Backfill name_key for any rows missing it.
    rows_missing_key = session.exec(
        select(Player).where(Player.name_key.is_(None))
    ).all()
    for p in rows_missing_key:
        p.name_key = name_key(p.full_name)
        session.add(p)
    if rows_missing_key:
        session.commit()

    # Group all rows by (name_key, tour).
    everyone = session.exec(select(Player)).all()
    groups: dict[tuple[str, Tour], list[Player]] = defaultdict(list)
    for p in everyone:
        if not p.name_key:
            continue
        groups[(p.name_key, p.tour)].append(p)

    merged = 0
    for (_, tour), members in groups.items():
        if len(members) < 2:
            continue
        canonical = _pick_canonical(session, members)
        for dup in members:
            if dup.id == canonical.id:
                continue
            _repoint(session, from_id=dup.id, to_id=canonical.id)
            _adopt_fuller_name(canonical, dup)
            # Promote any non-null fields from dup that canonical lacks
            # (a safety net for orthogonal info on dupes).
            for field in (
                "first_name", "last_name", "birth_date", "height_cm", "plays",
                "turned_pro", "sackmann_id", "api_tennis_id", "current_rank",
                "career_high_rank", "image_url", "bio", "wikidata_id",
                "wikipedia_url", "instagram_handle", "twitter_handle",
                "instagram_latest_post_url", "country_code",
            ):
                if getattr(canonical, field) is None and getattr(dup, field) is not None:
                    setattr(canonical, field, getattr(dup, field))
            session.delete(dup)
            merged += 1
        session.add(canonical)
        session.commit()
        log.info(
            "merged %d dup(s) into %s (%s, %s)",
            len(members) - 1, canonical.slug, canonical.full_name, tour.value,
        )
    return merged


def _name_fullness(name: str | None) -> int:
    """Count the full (non-initial) tokens in a name. "Jan Lennard Struff"
    → 3, "J-L. Struff" → 1. Used to keep the more human-readable spelling
    when a merge has to choose between an abbreviated and a spelled-out
    form of the same player."""
    if not name:
        return 0
    return sum(1 for t in (slugify(name) or "").split("-") if len(t) > 1)


def _adopt_fuller_name(canonical: Player, dup: Player) -> None:
    """If the dup spells the name out more fully than the canonical row
    (which we keep for its api_tennis_id, not its prettier name), take the
    dup's full_name so we don't regress "Jan Lennard Struff" to
    "J-L. Struff". Slug is intentionally left alone — it's a URL identity."""
    if _name_fullness(dup.full_name) > _name_fullness(canonical.full_name):
        canonical.full_name = dup.full_name
        canonical.name_key = name_key(dup.full_name)


_PROMOTABLE_FIELDS = (
    "first_name", "last_name", "birth_date", "height_cm", "plays",
    "turned_pro", "sackmann_id", "api_tennis_id", "current_rank",
    "career_high_rank", "image_url", "bio", "wikidata_id",
    "wikipedia_url", "instagram_handle", "twitter_handle",
    "instagram_latest_post_url", "country_code",
)


def merge_player_pair(session: Session, id_a: int, id_b: int) -> int | None:
    """Merge two known-duplicate player rows and commit. Returns the id of
    the surviving canonical row (None if either id is missing).

    A targeted alternative to the whole-DB `merge_*` sweeps for when you've
    already identified a specific duplicate pair (e.g. an api-tennis
    initials row and its Wikipedia spelled-out twin). Same canonical-pick,
    repoint, name-preservation and field-promotion rules as the sweeps.
    """
    a = session.get(Player, id_a)
    b = session.get(Player, id_b)
    if a is None or b is None:
        return None
    canonical = _pick_canonical(session, [a, b])
    dup = b if canonical.id == a.id else a
    _repoint(session, from_id=dup.id, to_id=canonical.id)
    _adopt_fuller_name(canonical, dup)
    for field in _PROMOTABLE_FIELDS:
        if getattr(canonical, field) is None and getattr(dup, field) is not None:
            setattr(canonical, field, getattr(dup, field))
    session.add(canonical)
    session.delete(dup)
    session.commit()
    log.info("merged player %d into %d (%s)", dup.id, canonical.id, canonical.full_name)
    return canonical.id


def _pick_canonical(session: Session, members: list[Player]) -> Player:
    """Score each candidate, return the highest. Ties broken by lowest id."""
    def score(p: Player) -> tuple[int, int, int]:
        match_count = session.exec(
            select(Match)
            .where(
                (Match.player1_id == p.id)
                | (Match.player2_id == p.id)
                | (Match.winner_id == p.id)
            )
        ).all()
        # Higher score = better candidate. We negate id to prefer smaller ids
        # (older rows) on ties.
        return (
            1 if p.api_tennis_id else 0,
            len(match_count),
            -(p.id or 0),
        )
    return max(members, key=score)


def _repoint(session: Session, from_id: int, to_id: int) -> None:
    """Update all FK references from one player id to another.

    Rankings are special: they have a (player_id, tour, week) natural key.
    Naively repointing creates duplicate rows when the canonical player
    already has a row for the same tour+week (the original cause of the
    "rank 26 listed twice" bug). For rankings we delete the dup row when
    that collision exists; otherwise we repoint normally.
    """
    matches_p1 = session.exec(select(Match).where(Match.player1_id == from_id)).all()
    for m in matches_p1:
        m.player1_id = to_id
        session.add(m)
    matches_p2 = session.exec(select(Match).where(Match.player2_id == from_id)).all()
    for m in matches_p2:
        m.player2_id = to_id
        session.add(m)
    matches_w = session.exec(select(Match).where(Match.winner_id == from_id)).all()
    for m in matches_w:
        m.winner_id = to_id
        session.add(m)
    matches_s = session.exec(select(Match).where(Match.server_player_id == from_id)).all()
    for m in matches_s:
        m.server_player_id = to_id
        session.add(m)

    rankings = session.exec(select(Ranking).where(Ranking.player_id == from_id)).all()
    for r in rankings:
        clash = session.exec(
            select(Ranking).where(
                Ranking.player_id == to_id,
                Ranking.tour == r.tour,
                Ranking.week == r.week,
            )
        ).first()
        if clash:
            # Canonical player already has a ranking for this tour+week.
            # Drop the dup; if the dup had a better rank/points, copy them
            # onto the canonical row first.
            if clash.rank > r.rank or (clash.points or 0) < (r.points or 0):
                clash.rank = r.rank
                clash.points = r.points
                session.add(clash)
            session.delete(r)
        else:
            r.player_id = to_id
            session.add(r)


def dedupe_rankings(session: Session) -> int:
    """One-shot cleanup of duplicate ranking rows that already exist on
    disk (left over from a prior _repoint that didn't dedupe). Keeps the
    row with the lowest rank for each (player_id, tour, week); deletes
    the rest. Returns count of rows deleted."""
    from collections import defaultdict
    by_key: dict[tuple[int, Tour, object], list[Ranking]] = defaultdict(list)
    for r in session.exec(select(Ranking)).all():
        by_key[(r.player_id, r.tour, r.week)].append(r)
    deleted = 0
    for rows in by_key.values():
        if len(rows) < 2:
            continue
        # Keep the best one (lowest rank wins; ties broken by lowest id).
        rows.sort(key=lambda r: (r.rank, r.id or 0))
        for dup in rows[1:]:
            session.delete(dup)
            deleted += 1
    if deleted:
        session.commit()
        log.info("rankings dedupe: deleted %d duplicate rows", deleted)
    return deleted


def _fuzzy_initial_match(name_a: str, name_b: str) -> bool:
    """True if these two names look like the same person where one form
    abbreviates one or more given-name tokens to initials.

    "A. Tabilo" vs "Alejandro Tabilo"            → True (one initial)
    "J-L. Struff" vs "Jan Lennard Struff"        → True (two initials)
    "Alex Smith" vs "Andrew Smith"               → False (different full first names)
    "T. Etcheverry" vs "Tomas Martin Etcheverry" → False (different token count)
    "J. L." vs "Jan Lennard"                     → False (no shared full-name anchor)

    Rules: same token count; every token pair is either identical or an
    initial-vs-full where the full token starts with the initial; at
    least one pair actually differs (else it's a plain name_key match,
    handled elsewhere); and at least one *identical* pair is a full token
    (len > 1) so the surname anchors the match. The anchor is what keeps
    a bare-initials form ("J. L.") from colliding with an unrelated full
    name — without a shared real word there's nothing tying them together.
    """
    if not name_a or not name_b:
        return False
    a = sorted(t for t in slugify(name_a).split("-") if t)
    b = sorted(t for t in slugify(name_b).split("-") if t)
    if not a or not b or len(a) != len(b):
        return False
    diff_pairs = 0
    shared_full_token = False
    for x, y in zip(a, b):
        if x == y:
            if len(x) > 1:
                shared_full_token = True
            continue
        # A differing pair is only allowed as initial-vs-full where the
        # full token starts with the initial letter.
        if len(x) == 1 and len(y) > 1 and y.startswith(x):
            diff_pairs += 1
        elif len(y) == 1 and len(x) > 1 and x.startswith(y):
            diff_pairs += 1
        else:
            return False
    return diff_pairs >= 1 and shared_full_token


def merge_initial_form_duplicates(session: Session) -> int:
    """Second-pass dedup: collapse "A. Tabilo" / "Alejandro Tabilo" pairs
    that the name_key pass missed because they tokenize differently.

    Within each tour, we only consider players whose full_name has a
    1-letter initial token (cheap filter, and the pattern we're targeting).
    For each, we look for any other player on the same tour whose tokens
    fuzzy-match. Found pairs get merged via the same `_repoint` machinery
    that handles word-order dups.

    Returns count of rows merged away.
    """

    def has_initial(name: str | None) -> bool:
        if not name:
            return False
        return any(len(t) == 1 for t in (slugify(name) or "").split("-") if t)

    # Snapshot a small immutable record per player up front. We must NOT
    # hold ORM references across delete-commit cycles — once a row is
    # deleted, accessing any attribute on its instance raises
    # ObjectDeletedError. Operate on (id, name, tour) tuples and re-fetch
    # only when we need to touch the row.
    snapshots: list[tuple[int, str, Tour]] = [
        (p.id, p.full_name, p.tour)
        for p in session.exec(select(Player)).all()
        if p.id is not None and p.full_name
    ]

    by_tour: dict[Tour, list[tuple[int, str]]] = {}
    for pid, name, tour in snapshots:
        by_tour.setdefault(tour, []).append((pid, name))

    merged = 0
    for tour, pool in by_tour.items():
        initials = [(pid, name) for pid, name in pool if has_initial(name)]
        if not initials:
            continue
        # Compare initials against every other player in the tour (full
        # names AND other initial-form rows for rare cross-abbrev cases).
        candidates = pool

        already_merged: set[int] = set()
        for ini_id, ini_name in initials:
            if ini_id in already_merged:
                continue
            for other_id, other_name in candidates:
                if other_id == ini_id or other_id in already_merged:
                    continue
                if not _fuzzy_initial_match(ini_name, other_name):
                    continue

                # Re-fetch fresh ORM rows. The earlier session.commit()s in
                # this loop expire instances; re-fetching dodges stale state.
                ini_row = session.get(Player, ini_id)
                other_row = session.get(Player, other_id)
                if ini_row is None or other_row is None:
                    continue

                canonical = _pick_canonical(session, [ini_row, other_row])
                dup = other_row if canonical.id == ini_row.id else ini_row
                dup_id = dup.id
                canonical_id = canonical.id
                if dup_id is None or canonical_id is None:
                    continue

                _repoint(session, from_id=dup_id, to_id=canonical_id)
                _adopt_fuller_name(canonical, dup)
                # Promote any non-null fields from dup that canonical lacks.
                for field in (
                    "first_name", "last_name", "birth_date", "height_cm", "plays",
                    "turned_pro", "sackmann_id", "api_tennis_id", "current_rank",
                    "career_high_rank", "image_url", "bio", "wikidata_id",
                    "wikipedia_url", "instagram_handle", "twitter_handle",
                    "instagram_latest_post_url", "country_code",
                ):
                    if getattr(canonical, field) is None and getattr(dup, field) is not None:
                        setattr(canonical, field, getattr(dup, field))
                canonical.name_key = name_key(canonical.full_name)
                session.add(canonical)
                session.delete(dup)
                session.commit()
                already_merged.add(dup_id)
                merged += 1
                log.info(
                    "fuzzy-merged %s ← (id=%d) (%s)",
                    canonical.full_name, dup_id, tour.value,
                )
                # If `ini` itself was the dup, stop iterating its candidates.
                if dup_id == ini_id:
                    break
    return merged
