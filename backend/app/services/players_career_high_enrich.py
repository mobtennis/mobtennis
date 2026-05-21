"""Career-high singles ranking enrichment via Wikipedia infobox.

The static seed in `player_career_seed.py` covers the top ~40 active
players and a curated set of legends. This module fills in everyone
else by reading their Wikipedia article's infobox `careerhighsingles`
field — Wikipedia's "Career high" stat for tennis players is wrapped
in `{{Infobox tennis biography ... | careerhighsingles = '''No. 7'''}}`
or close variants in nearly every article, so a regex pass over the
lead section's wikitext is enough.

Pre-req: `Player.wikipedia_url` is populated (set by players_bio_enrich
which is already running weekly).

Strategy:
  1. Pull the lead-section wikitext via `action=parse&prop=wikitext&section=0`
     (one HTTP call per player; ~few-KB response).
  2. Regex out the careerhighsingles value. Handle the common shapes:
       | careerhighsingles = '''No. 7''' (1 March 2021)
       | careerhighsingles  =   No. 1
       | careerhighsingles=World No. 23
  3. Apply only when the result is lower (= better) than what we have
     stored — same guard as the static seed.
"""

from __future__ import annotations

import asyncio
import logging
import re
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
    """Returns True if we updated career_high_rank, False otherwise."""
    if not player.wikipedia_url:
        return False
    title = _title_from_url(player.wikipedia_url)
    if not title:
        return False

    wikitext = await _fetch_lead_wikitext(title, client)
    if not wikitext:
        return False
    new_ch = parse_career_high(wikitext)
    if new_ch is None:
        return False

    current = player.career_high_rank
    if current is not None and current <= new_ch:
        return False  # already have a better (= lower) value
    player.career_high_rank = new_ch
    session.add(player)
    session.commit()
    return True


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
