"""Repair Player.bio text where the stored content doesn't describe the
player. Companion to players_career_high_enrich.py — same pattern:
validate that the article actually belongs to the player (surname
appears in the text), and when it doesn't, fetch the right one.

Why this exists separately from players_bio_enrich.py:
  - bio_enrich uses Player.wikidata_id → sitelink → summary. If
    wikidata_id was set wrong by the earlier socials-enrich pass
    (which happened often for abbreviated-name players like
    "D. Kasatkina"), bio ended up describing the wrong article.
  - The career-high enrichment self-heals wikipedia_url via a surname-
    validated Wikipedia search, but doesn't re-fetch bio.
  - This service uses the (now-correct) wikipedia_url to refresh bio
    text, OR falls back to the same surname-aware search.

Idempotent. Cheap (one HTTP call per repaired player). Safe to run
ad-hoc.
"""

from __future__ import annotations

import asyncio
import logging
import unicodedata
from urllib.parse import unquote

import httpx
from sqlmodel import Session, select

from app.models.player import Player
from app.services.players_career_high_enrich import (
    _expected_surname,
    _find_player_article,
    _is_player_bio,
    _title_matches_player,
)
from app.services.wikidata import UA, WIKI_SUMMARY_URL

log = logging.getLogger(__name__)

_DELAY_S = 0.5
_MAX_BIO_CHARS = 480


def _normalize(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def _bio_about_player(bio: str | None, player: Player) -> bool:
    """True if the stored bio text plausibly describes this player.

    We check that the player's surname (or its accent-stripped form)
    appears in the bio. Tightens further: for compound surnames like
    'Bautista-Agut' we also accept either single token to avoid false
    negatives on bios that hyphenate differently."""
    if not bio:
        return False
    bio_n = _normalize(bio)
    parts = (player.full_name or "").split()
    if not parts:
        return True  # no signal, don't auto-flag

    # Get the surname tokens (everything after an initial-only first token).
    if len(parts) >= 2 and len(parts[0]) <= 2 and parts[0].endswith("."):
        surname_parts = parts[1:]
    elif len(parts) >= 2:
        # Heuristic: assume last 1-2 tokens are surname. Most tennis
        # surnames are single-token; compound ones (De Minaur, Haddad
        # Maia, Bautista-Agut) span two.
        surname_parts = parts[-2:] if len(parts) >= 3 or "-" in parts[-2] or len(parts[-2]) <= 4 else parts[-1:]
    else:
        surname_parts = parts

    # Match if ANY surname token (≥ 3 chars to avoid false positives
    # on common short words) appears in the bio.
    for token in surname_parts:
        norm = _normalize(token).replace("-", " ")
        for chunk in norm.split():
            if len(chunk) >= 3 and chunk in bio_n:
                return True
    return False


def _trim(text: str | None, limit: int = _MAX_BIO_CHARS) -> str | None:
    if not text:
        return None
    para = text.split("\n\n")[0].strip()
    if len(para) <= limit:
        return para
    cut = para[:limit]
    last_period = cut.rfind(". ")
    if last_period > limit * 0.6:
        return cut[: last_period + 1]
    return cut.rstrip() + "…"


def _title_from_url(url: str) -> str | None:
    marker = "/wiki/"
    idx = url.find(marker)
    if idx < 0:
        return None
    return unquote(url[idx + len(marker):]).split("#", 1)[0]


async def _fetch_summary(title: str, client: httpx.AsyncClient) -> str | None:
    """Wikipedia REST summary — short, plain extract suitable for the bio
    blurb. Returns None on miss."""
    r = await client.get(f"{WIKI_SUMMARY_URL}/{title.replace(' ', '_')}")
    if r.status_code != 200:
        return None
    return r.json().get("extract")


async def repair_one(
    session: Session, player: Player, client: httpx.AsyncClient,
) -> bool:
    """Fix bio for one player. Returns True if updated."""
    if _bio_about_player(player.bio, player):
        return False

    expected = _expected_surname(player)
    new_bio: str | None = None

    # Try the stored wikipedia_url first — career-high enrichment may
    # have already corrected it.
    if player.wikipedia_url:
        title = _title_from_url(player.wikipedia_url)
        if title and _title_matches_player(title, expected):
            text = await _fetch_summary(title, client)
            new_bio = _trim(text)
            if new_bio and not _bio_about_player(new_bio, player):
                new_bio = None  # extract didn't actually describe this player

    # Fall back to a full Wikipedia search.
    if not new_bio:
        found = await _find_player_article(player, client)
        if found:
            new_title, _ = found
            new_url = f"https://en.wikipedia.org/wiki/{new_title.replace(' ', '_')}"
            text = await _fetch_summary(new_title, client)
            new_bio = _trim(text)
            if new_bio and _bio_about_player(new_bio, player):
                # Also write back the corrected URL.
                player.wikipedia_url = new_url
            else:
                new_bio = None

    if not new_bio:
        return False
    log.info(
        "%s: bio repaired (%d chars)\n  %r",
        player.slug, len(new_bio), new_bio[:120],
    )
    player.bio = new_bio
    session.add(player)
    session.commit()
    return True


async def repair_top_n(
    session: Session, *, n: int = 250,
) -> tuple[int, int, int]:
    """Walk top-N-per-tour players by current rank. Returns
    (attempted, repaired, untouched)."""
    candidates = session.exec(
        select(Player)
        .where(Player.current_rank.is_not(None))
        .where(Player.current_rank <= n)
        .where(Player.bio.is_not(None))
        .order_by(Player.current_rank)
    ).all()
    # Filter to actually-suspect bios up front so we don't do HTTP
    # work for the 350+ players whose bios are fine.
    suspect = [p for p in candidates if not _bio_about_player(p.bio, p)]
    log.info(
        "of %d players with bios, %d look suspect (surname missing from text)",
        len(candidates), len(suspect),
    )
    attempted = repaired = untouched = 0
    async with httpx.AsyncClient(
        headers={"User-Agent": UA}, timeout=15.0,
    ) as client:
        for i, p in enumerate(suspect):
            attempted += 1
            try:
                if await repair_one(session, p, client):
                    repaired += 1
                else:
                    untouched += 1
            except Exception:
                log.exception("bio repair failed for %s", p.slug)
                untouched += 1
            if i + 1 < len(suspect):
                await asyncio.sleep(_DELAY_S)
    return attempted, repaired, untouched
