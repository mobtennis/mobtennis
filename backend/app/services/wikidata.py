"""Wikidata client for player social handles + tournament dates.

Path:  name → Wikipedia article → wikibase_item (Qid) → Wikidata claims

Properties we extract:
  P2003 — Instagram username       (player socials)
  P2002 — Twitter (X) username     (player socials)
  P580  — start time               (tournament dates)
  P582  — end time                 (tournament dates)

Wikipedia + Wikidata both ask for a meaningful User-Agent. Callers should
rate-limit (~500ms) to be polite.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import httpx

UA = "Tennismob/0.1 (https://tennismob.app; bot@mob.tennis)"
WIKI_SEARCH_URL = "https://en.wikipedia.org/w/api.php"
WIKI_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary"
WIKIDATA_ENTITY_URL = "https://www.wikidata.org/wiki/Special:EntityData"


@dataclass
class PlayerSocials:
    wikidata_id: str
    wikipedia_title: str
    instagram: str | None
    twitter: str | None


def _claim_value(entity: dict, prop: str) -> str | None:
    """Pull the mainsnak string value for a Wikidata property, if present."""
    claims = entity.get("claims", {}).get(prop, [])
    if not claims:
        return None
    val = claims[0].get("mainsnak", {}).get("datavalue", {}).get("value")
    if isinstance(val, str):
        return val.strip() or None
    return None


_SEARCH_LIMIT = 5
# Skip sub-articles — for famous players Wikipedia surfaces "X career
# statistics", "2026 X tennis season" alongside the main bio. We want the bio.
_TITLE_SKIP_MARKERS = (
    "career statistics", "tennis season", "Olympics", "Davis Cup",
    "head-to-head", "rivalry", "performance timeline",
)


async def _check_candidate(
    title: str, client: httpx.AsyncClient
) -> tuple[str, dict] | None:
    """Resolves an article title to its Wikidata entity *iff* P641 (sport)
    is Q847 (tennis). Returns (qid, entity) on hit, None otherwise.
    """
    title_url = title.replace(" ", "_")
    pr = await client.get(f"{WIKI_SUMMARY_URL}/{title_url}")
    if pr.status_code != 200:
        return None
    summary = pr.json()
    if summary.get("type") == "disambiguation":
        return None
    qid = summary.get("wikibase_item")
    if not qid:
        return None

    er = await client.get(f"{WIKIDATA_ENTITY_URL}/{qid}.json")
    if er.status_code != 200:
        return None
    ent = er.json().get("entities", {}).get(qid)
    if not ent:
        return None

    sport_claims = ent.get("claims", {}).get("P641", [])
    is_tennis = any(
        c.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id") == "Q847"
        for c in sport_claims
    )
    if not is_tennis:
        return None
    return qid, ent


# ---- Tournament dates -----------------------------------------------------


@dataclass
class TournamentDates:
    start_date: date | None
    end_date: date | None


def _parse_wikidata_time(value: dict) -> date | None:
    """Wikidata stores datetimes as `{'time': '+2026-05-04T00:00:00Z',
    'precision': 11, ...}` — precision 11 = day, 10 = month, 9 = year.
    Anything coarser than day is useless to us."""
    if not isinstance(value, dict):
        return None
    if value.get("precision", 0) < 11:
        return None
    raw = value.get("time")
    if not raw:
        return None
    s = raw.lstrip("+").rstrip("Z")
    try:
        return datetime.fromisoformat(s).date()
    except ValueError:
        return None


def _claim_date(entity: dict, prop: str) -> date | None:
    claims = entity.get("claims", {}).get(prop, [])
    if not claims:
        return None
    return _parse_wikidata_time(
        claims[0].get("mainsnak", {}).get("datavalue", {}).get("value")
    )


def _entity_is_tennis(ent: dict) -> bool:
    """P641 (sport) = Q847 (tennis), or P31 (instance of) tagged as a
    tennis tournament edition. Without this check, US Open / Italian Open
    can match same-name golf or motorsports articles."""
    sport_claims = ent.get("claims", {}).get("P641", [])
    if any(
        c.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id") == "Q847"
        for c in sport_claims
    ):
        return True
    instance_claims = ent.get("claims", {}).get("P31", [])
    tennis_qids = {"Q13219666", "Q47089"}  # tennis tournament edition / tennis tournament
    return any(
        c.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id") in tennis_qids
        for c in instance_claims
    )


_MONTHS: dict[str, int] = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _parse_date_range_from_text(text: str | None, year: int) -> TournamentDates | None:
    """Best-effort regex extraction from Wikipedia summary prose, e.g.:
      "between 5 and 17 May 2026"
      "from 5 to 17 May 2026"
      "5–17 May 2026"
      "May 5 to 17, 2026"
      "29 April to 11 May 2026"   (cross-month)
    Wikidata's structured P580/P582 is often empty for current-year editions
    even when the prose has the dates, so this fills that gap."""
    import re  # local import — only used during enrichment runs
    if not text:
        return None
    months = "|".join(_MONTHS.keys())

    # Same-month: "5 [-/–/and/to] 17 May 2026"
    hit = re.search(
        rf"\b(\d{{1,2}})\s*(?:[–-]|to|and)\s*(\d{{1,2}})\s+({months})\s+(\d{{4}})\b",
        text, re.IGNORECASE,
    )
    if hit:
        d1, d2, mon, yr = int(hit.group(1)), int(hit.group(2)), hit.group(3).lower(), int(hit.group(4))
        if yr == year and mon in _MONTHS:
            try:
                return TournamentDates(date(yr, _MONTHS[mon], d1), date(yr, _MONTHS[mon], d2))
            except ValueError:
                pass

    # Cross-month: "29 April to 11 May 2026"
    hit = re.search(
        rf"\b(\d{{1,2}})\s+({months})\s+(?:[–-]|to|and)\s+(\d{{1,2}})\s+({months})\s+(\d{{4}})\b",
        text, re.IGNORECASE,
    )
    if hit:
        d1, mon1, d2, mon2, yr = (
            int(hit.group(1)), hit.group(2).lower(),
            int(hit.group(3)), hit.group(4).lower(), int(hit.group(5)),
        )
        if yr == year and mon1 in _MONTHS and mon2 in _MONTHS:
            try:
                return TournamentDates(date(yr, _MONTHS[mon1], d1), date(yr, _MONTHS[mon2], d2))
            except ValueError:
                pass

    # US-style: "May 5 [-/to/and] 17, 2026"
    hit = re.search(
        rf"\b({months})\s+(\d{{1,2}})\s*(?:[–-]|to|and)\s*(\d{{1,2}}),?\s+(\d{{4}})\b",
        text, re.IGNORECASE,
    )
    if hit:
        mon, d1, d2, yr = hit.group(1).lower(), int(hit.group(2)), int(hit.group(3)), int(hit.group(4))
        if yr == year and mon in _MONTHS:
            try:
                return TournamentDates(date(yr, _MONTHS[mon], d1), date(yr, _MONTHS[mon], d2))
            except ValueError:
                pass

    return None


async def fetch_tournament_dates(
    name: str,
    year: int,
    client: httpx.AsyncClient | None = None,
) -> TournamentDates | None:
    """Look up an edition's start/end dates.

    Two-source strategy because Wikidata's structured P580/P582 is reliably
    empty for *current-year* editions (the case we care about most):
      1. Wikidata P580 (start time) and P582 (end time) — best when present.
      2. Fall back to parsing the date range out of the Wikipedia summary
         prose. Editors fill that in well before the structured claims.

    Searches for `{year} {name} tennis` to bias toward tennis articles, and
    only accepts entities flagged as tennis via P641 or P31 — guards against
    a same-name golf or motorsports event.
    """
    own = client is None
    if own:
        client = httpx.AsyncClient(headers={"User-Agent": UA}, timeout=10.0)
    try:
        sr = await client.get(
            WIKI_SEARCH_URL,
            params={
                "action": "query", "list": "search",
                "srsearch": f"{year} {name} tennis",
                "srlimit": _SEARCH_LIMIT, "format": "json",
            },
        )
        if sr.status_code != 200:
            return None
        hits = sr.json().get("query", {}).get("search", [])
        for hit in hits:
            title = hit.get("title", "")
            if not title or str(year) not in title:
                continue
            title_url = title.replace(" ", "_")
            pr = await client.get(f"{WIKI_SUMMARY_URL}/{title_url}")
            if pr.status_code != 200:
                continue
            summary = pr.json()
            qid = summary.get("wikibase_item")
            if not qid:
                continue
            er = await client.get(f"{WIKIDATA_ENTITY_URL}/{qid}.json")
            if er.status_code != 200:
                continue
            ent = er.json().get("entities", {}).get(qid)
            if not ent or not _entity_is_tennis(ent):
                continue

            # Source #1: Wikidata structured claims.
            start = _claim_date(ent, "P580")
            end = _claim_date(ent, "P582")
            if start is not None or end is not None:
                return TournamentDates(start_date=start, end_date=end)

            # Source #2: prose extraction from the Wikipedia summary.
            from_prose = _parse_date_range_from_text(summary.get("extract"), year)
            if from_prose is not None:
                return from_prose
        return None
    finally:
        if own:
            await client.aclose()


# ---- Player socials -------------------------------------------------------


async def fetch_player_socials(
    name: str,
    client: httpx.AsyncClient | None = None,
) -> PlayerSocials | None:
    """Return socials for the most likely tennis-player Wikipedia article.

    Strategy: pull the top _SEARCH_LIMIT search hits and walk them until we
    find one whose Wikidata entity has sport=tennis. Without this loop, a
    famous player's name search can return a sub-article ("career statistics",
    "<year> tennis season") at position 1, which has no useful Wikidata link.
    No disambiguator suffix — for famous players that pushes the bio further
    down; the sport-check is enough to prevent same-name false positives.
    """
    own = client is None
    if own:
        client = httpx.AsyncClient(headers={"User-Agent": UA}, timeout=10.0)
    try:
        sr = await client.get(
            WIKI_SEARCH_URL,
            params={
                "action": "query", "list": "search",
                "srsearch": name, "srlimit": _SEARCH_LIMIT, "format": "json",
            },
        )
        sr.raise_for_status()
        hits = sr.json().get("query", {}).get("search", [])

        for hit in hits:
            title = hit.get("title", "")
            if not title:
                continue
            tl = title.lower()
            if any(m in tl for m in (m.lower() for m in _TITLE_SKIP_MARKERS)):
                continue
            result = await _check_candidate(title, client)
            if result is None:
                continue
            qid, ent = result
            return PlayerSocials(
                wikidata_id=qid,
                wikipedia_title=title,
                instagram=_claim_value(ent, "P2003"),
                twitter=_claim_value(ent, "P2002"),
            )
        return None
    finally:
        if own:
            await client.aclose()
