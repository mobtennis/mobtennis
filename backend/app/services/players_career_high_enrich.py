"""Career-high singles ranking enrichment via Wikipedia infobox.

The static seed in `player_career_seed.py` covers the top ~40 active
players and a curated set of legends. This module fills in everyone
else by reading their Wikipedia article's infobox `highestsinglesranking`
field — wrapped in a wikilink to "List of ATP/WTA number 1 ranked
singles tennis players" in modern articles, or plain `careerhighsingles`
in older ones.

Self-heals upstream wrong matches: when `Player.wikipedia_url` was set
by players_bio_enrich to a non-player article (tournament page,
season page, list article — common for players whose api-tennis name
is abbreviated like "D. Kasatkina"), this module re-searches
Wikipedia using a smarter query, validates the result is a real
tennis-biography article, and writes the correct URL back to the
Player row.

Strategy per player:
  1. If we already have a wikipedia_url, fetch its lead-section wikitext.
  2. Confirm the wikitext is a tennis-biography (contains an Infobox
     tennis biography template). If yes, regex the career-high.
  3. If not — wrong URL or list article — search Wikipedia with the
     player's last name + "tennis" (and country code as a tiebreaker),
     validate each candidate, repair `wikipedia_url` if a match is
     found.
  4. Apply career_high_rank only when lower (= better) than the stored
     value.
"""

from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from urllib.parse import unquote

import httpx
from sqlmodel import Session, select

from app.models.player import Player
from app.services.wikidata import UA

log = logging.getLogger(__name__)

_DELAY_S = 0.5
_TIMEOUT_S = 10.0
_WIKI_API = "https://en.wikipedia.org/w/api.php"

# Real-world Wikipedia tennis-infobox usage (sampled May 2026 across
# Djokovic, Sabalenka, Świątek, plus dozens of mid-tier players):
#
#   | highestsinglesranking = [[List of ATP number 1 ranked singles tennis players|No. '''1''']] (4 July 2011)
#   | highestsinglesranking         = [[List of WTA number 1 ranked singles tennis players|No. '''1''']] (11 Sep 2023)
#   | highestsinglesranking  = No. 23 (5 March 2018)
#   | careerhighsingles = '''No. 7''' (1 March 2021)
#
# So we need to handle BOTH common field names (`highestsinglesranking`
# is the modern one, `careerhighsingles` is the older form), AND look
# for `No. N` anywhere after the `=` regardless of whether it's wrapped
# in a wikilink `[[...|No. N]]`, boldface `'''No. N'''`, plain "World No.",
# or a date qualifier follows.
_CAREER_HIGH_RE = re.compile(
    # Field name (either form), then anything up to "No. N" — the value
    # may be wrapped in a wikilink like `[[List of ATP number 1...|No. 1]]`
    # so we don't exclude `|` from the skip; only newlines (which mark
    # the next infobox field). We DO NOT alternate "number" with "No." —
    # the wikilink target reads "ATP number 1 ranked..." and would
    # spuriously match.
    r"(?:highestsinglesranking|careerhighsingles)\s*=\s*[^}\n]*?"
    r"no\.?\s*'*\s*(\d{1,3})",
    re.IGNORECASE,
)


def _title_from_url(url: str) -> str | None:
    """Extract a Wikipedia article title from a wikipedia_url."""
    marker = "/wiki/"
    idx = url.find(marker)
    if idx < 0:
        return None
    return unquote(url[idx + len(marker):]).split("#", 1)[0]


async def _fetch_lead_wikitext(title: str, client: httpx.AsyncClient) -> str | None:
    """Lead section only — keeps responses small and avoids parsing the
    whole article. Wikipedia's infobox is part of section 0."""
    params = {
        "action": "parse",
        "page": title,
        "prop": "wikitext",
        "section": 0,
        "format": "json",
        "redirects": 1,
    }
    r = await client.get(_WIKI_API, params=params)
    if r.status_code != 200:
        return None
    j = r.json()
    return j.get("parse", {}).get("wikitext", {}).get("*")


# Substring tests for "is this a tennis player biography page?". A real
# bio carries one of these infobox templates near the top.
_PLAYER_INFOBOX_MARKERS = (
    "infobox tennis biography",
    "infobox tennis player",
)


def _is_player_bio(wikitext: str | None) -> bool:
    if not wikitext:
        return False
    low = wikitext.lower()
    return any(m in low for m in _PLAYER_INFOBOX_MARKERS)


# Search-result candidate ranking. Wikipedia returns a list of titles
# matching the query; we walk them in order and accept the first one
# whose lead-section wikitext is a tennis biography. Cap at 5 to bound
# total HTTP work per player.
_MAX_SEARCH_CANDIDATES = 5


async def _wiki_search(
    query: str, client: httpx.AsyncClient, *, limit: int = _MAX_SEARCH_CANDIDATES,
) -> list[str]:
    """Returns a list of Wikipedia article titles matching the query,
    most relevant first. Empty list on failure."""
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": limit,
        "format": "json",
    }
    try:
        r = await client.get(_WIKI_API, params=params)
        if r.status_code != 200:
            return []
    except Exception:
        return []
    j = r.json()
    return [hit["title"] for hit in j.get("query", {}).get("search", [])]


def _search_terms(player: Player) -> list[str]:
    """Generate candidate Wikipedia search queries for a player.

    Most players have a usable full_name. The tricky ones are
    api-tennis abbreviations ("D. Kasatkina") — we strip the initial
    and search by surname plus disambiguators. Country code is a
    strong tiebreaker when present.
    """
    terms: list[str] = []
    name = (player.full_name or "").strip()
    if name:
        parts = name.split()
        # Abbreviated form: first token is a single letter + period.
        if len(parts) >= 2 and len(parts[0]) <= 2 and parts[0].endswith("."):
            last_name = " ".join(parts[1:])
            if player.country_code:
                terms.append(f"{last_name} tennis {player.country_code}")
            terms.append(f"{last_name} tennis")
            terms.append(last_name)
        else:
            # Full name — search it directly, plus a "tennis" variant
            # to push the player bio above tournament/season pages
            # named after the same player.
            terms.append(f"{name} tennis")
            terms.append(name)
    # Fallback: derive a surname guess from the slug. Slugs are
    # hyphenated; the tail token is usually the last name.
    slug = (player.slug or "").strip()
    if slug:
        tail = slug.split("-")[-1].replace("_", " ").title()
        if tail and tail not in " ".join(terms):
            terms.append(f"{tail} tennis")
    return terms


def _normalize(s: str) -> str:
    """Lowercase + accent-strip for fuzzy comparison. "Sebastián" → "sebastian"."""
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def _expected_surname(player: Player) -> str | None:
    """Best-effort surname token to look for in candidate article titles.

    Handles three input shapes:
      - Full name "Sebastian Baez" → "baez"
      - Abbreviated "S. Baez"      → "baez"
      - Compound  "B. Haddad Maia" → "haddad maia" (preserves multi-token surnames)

    The compound case matters: matching just "maia" would over-accept
    other "Maia" players. We use everything after the first-name token.
    """
    name = (player.full_name or "").strip()
    parts = name.split()
    if len(parts) >= 2 and len(parts[0]) <= 2 and parts[0].endswith("."):
        # Abbreviated first name — take all the rest as the surname.
        return _normalize(" ".join(parts[1:]))
    if len(parts) >= 2:
        # Take the last 1-2 tokens depending on length. Most compound
        # surnames in tennis are two tokens (Haddad Maia, Auger-Aliassime
        # as a single token, De Minaur, etc.). Joining the last two
        # captures "De Minaur" / "Haddad Maia" but not "Carlos Alcaraz".
        # Heuristic: if the second-to-last token is short ("De", "Van",
        # "Da", "Le", "Auger-") OR if the article we'll match is likely
        # to be "Last1 Last2", include both. Otherwise just take the
        # last token.
        if len(parts[-2]) <= 4 or "-" in parts[-2]:
            return _normalize(" ".join(parts[-2:]))
        return _normalize(parts[-1])
    # Fallback: slug tail (drop the initial-only first segment).
    slug = (player.slug or "").strip()
    if slug:
        slug_parts = slug.split("-")
        # Skip the leading single-letter initial like "d-kasatkina".
        if len(slug_parts) >= 2 and len(slug_parts[0]) <= 2:
            return _normalize(" ".join(slug_parts[1:]))
        return _normalize(" ".join(slug_parts))
    return None


def _title_matches_player(title: str, expected_surname: str | None) -> bool:
    """True if the candidate Wikipedia article title plausibly belongs
    to this player — i.e. its title contains the expected surname after
    accent-normalisation. Without this guard, a tennis-bio article for
    a different player can be accepted just because it happens to rank
    first in the Wikipedia search (e.g. searching "Borges tennis BRA"
    can surface Rafael Nadal's article when "Borges" appears anywhere
    in Nadal's lead)."""
    if not expected_surname:
        # No surname signal — don't match anything by accident.
        return False
    return expected_surname in _normalize(title)


async def _find_player_article(
    player: Player, client: httpx.AsyncClient,
) -> tuple[str, str] | None:
    """Walk our candidate queries, fetch the lead wikitext of each
    search hit, and return (title, wikitext) for the first hit that
    is BOTH a tennis bio AND has the expected surname in its title.
    None if nothing matches both criteria."""
    expected = _expected_surname(player)
    seen: set[str] = set()
    for query in _search_terms(player):
        for title in await _wiki_search(query, client):
            if title in seen:
                continue
            seen.add(title)
            if not _title_matches_player(title, expected):
                continue
            wt = await _fetch_lead_wikitext(title, client)
            if _is_player_bio(wt):
                return title, wt or ""
    return None


def parse_career_high(wikitext: str) -> int | None:
    """Pulls the singles career-high integer out of the infobox wikitext.
    Returns None if the field is absent or unparseable."""
    if not wikitext:
        return None
    m = _CAREER_HIGH_RE.search(wikitext)
    if not m:
        return None
    try:
        n = int(m.group(1))
    except ValueError:
        return None
    # Sanity: tennis singles ranks rarely go below #1 (no #0) or above
    # ~3000. Anything outside that window is misparsed boilerplate.
    if 1 <= n <= 3000:
        return n
    return None


async def enrich_one(
    session: Session, player: Player, client: httpx.AsyncClient,
) -> bool:
    """Returns True if we updated career_high_rank, False otherwise.

    Side-effect: when the stored wikipedia_url points at a non-player
    page (tournament page, season page, list article — a known
    failure mode of the abbreviated-name bio matching upstream),
    re-searches Wikipedia and writes the correct URL back to the
    player row. The career-high then gets read from the corrected
    article in the same pass.
    """
    wikitext: str | None = None

    # 1. Try the stored URL first.
    if player.wikipedia_url:
        title = _title_from_url(player.wikipedia_url)
        if title:
            wikitext = await _fetch_lead_wikitext(title, client)

    # 2. If we have no wikitext, or it's not a tennis bio, hunt.
    repaired = False
    if not _is_player_bio(wikitext):
        found = await _find_player_article(player, client)
        if found is None:
            return False
        new_title, wikitext = found
        new_url = f"https://en.wikipedia.org/wiki/{new_title.replace(' ', '_')}"
        if new_url != player.wikipedia_url:
            log.info(
                "%s: repairing wikipedia_url\n  old: %s\n  new: %s",
                player.slug, player.wikipedia_url, new_url,
            )
            player.wikipedia_url = new_url
            repaired = True

    new_ch = parse_career_high(wikitext)
    if new_ch is None:
        # Save the repaired URL even if the article lacks the field.
        if repaired:
            session.add(player)
            session.commit()
        return False

    current = player.career_high_rank
    changed = False
    if current is None or current > new_ch:
        player.career_high_rank = new_ch
        changed = True
    if changed or repaired:
        session.add(player)
        session.commit()
    return changed


async def enrich_top_n(
    session: Session, *, n: int = 200,
) -> tuple[int, int, int]:
    """Walks top-N ATP + WTA players by current rank, fills career_high_rank
    from Wikipedia's infobox where ours is missing or worse.

    Returns (attempted, updated, skipped_no_better).
    """
    # Top N by current rank, ATP + WTA combined. Players without a
    # current_rank (retired, low-ranked) are skipped — the seed covers
    # the curated legends.
    candidates = session.exec(
        select(Player)
        .where(Player.current_rank.is_not(None))
        .where(Player.wikipedia_url.is_not(None))
        .order_by(Player.current_rank)
        .limit(n * 2)  # n ATP + n WTA across both tours
    ).all()

    attempted = updated = skipped = 0
    async with httpx.AsyncClient(
        headers={"User-Agent": UA}, timeout=_TIMEOUT_S,
    ) as client:
        for i, p in enumerate(candidates):
            attempted += 1
            try:
                changed = await enrich_one(session, p, client)
                if changed:
                    updated += 1
                else:
                    skipped += 1
            except Exception:
                log.exception("career-high enrich failed for %s", p.slug)
                skipped += 1
            if i + 1 < len(candidates):
                await asyncio.sleep(_DELAY_S)
    return attempted, updated, skipped
