"""Tournament categorization by name.

api-tennis doesn't return tier metadata on the match row — we infer it from
the tournament name. Curated lists for the high tiers (where misclassification
is most visible); pattern matching for the long tail (Challenger/ITF).
"""

from __future__ import annotations

import re

from app.models.player import Tour
from app.models.tournament import TournamentCategory

# Names that match these are slams regardless of year
GRAND_SLAMS = {"australian open", "roland garros", "french open", "wimbledon", "us open"}

# ATP Masters 1000 — exact city/event names. Doha is included as it joined the rotation.
ATP_1000_NAMES = {
    "indian wells", "bnp paribas open",
    "miami", "miami open",
    "monte-carlo", "monte carlo",
    "madrid", "mutua madrid",
    "rome", "italian open", "internazionali bnl",
    "toronto", "montreal", "canadian open", "national bank open",
    "cincinnati", "western & southern",
    "shanghai", "rolex shanghai",
    "paris", "rolex paris", "paris-bercy", "paris bercy",
    "doha", "qatar open",
}

# WTA 1000 venues (overlaps with ATP for combined events)
WTA_1000_NAMES = ATP_1000_NAMES | {
    "beijing", "china open",
    "wuhan", "dongfeng motor wuhan",
    "guadalajara", "akron guadalajara",
    "dubai", "dubai duty free",
    "doha", "qatar total",  # WTA 1000 in odd years
}

ATP_500_NAMES = {
    "rotterdam", "abn amro",
    "rio open",
    "dubai duty free",  # ATP side of combined
    "acapulco", "abierto mexicano",
    "barcelona", "godo", "conde de godo",
    "munich", "bmw open",
    "queens club", "cinch championships",
    "halle", "terra wortmann",
    "hamburg", "german open tennis",
    "washington", "citi open",
    "tokyo", "kinoshita",
    "vienna", "erste bank",
    "basel", "swiss indoors",
}

WTA_500_NAMES = {
    "abu dhabi", "mubadala abu dhabi",
    "adelaide international",
    "linz", "upper austria ladies",
    "stuttgart", "porsche tennis grand prix",
    "berlin", "ecotrans",
    "eastbourne", "rothesay",
    "san diego", "san diego open",
    "tokyo", "toray pan pacific",
    "ningbo",
    "cancun",
    "merida",
    "charleston", "credit one",
}

ATP_FINALS_NAMES = {"atp finals", "nitto atp finals", "atp world tour finals", "next gen atp finals"}
WTA_FINALS_NAMES = {"wta finals", "wta championships", "wta elite trophy"}

DAVIS_CUP_PATTERNS = ("davis cup",)
BJK_CUP_PATTERNS = ("billie jean king cup", "fed cup", "bjk cup")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def _is_lower_tier_by_name(n: str) -> TournamentCategory | None:
    """Detect ITF / Challenger from name patterns alone. Crucial that this
    runs BEFORE upper-tier substring matches — without it, "ITF W75 Rome"
    leaks into wta_1000 because "rome" appears in the name. Patterns:
      - "itf" anywhere in the name
      - M15/M25/M40/W15/W25/W35/W50/W60/W75/W100, optionally followed by '+H'
      - "challenger" anywhere, or "ch." / "ch " prefix
    """
    if "itf" in n:
        return TournamentCategory.ITF
    if re.search(r"\bm\d{2,3}\b", n) or re.search(r"\bw\d{2,3}(?:\+h)?\b", n):
        return TournamentCategory.ITF
    if "challenger" in n or n.startswith("ch.") or n.startswith("ch "):
        return TournamentCategory.CHALLENGER
    return None


def _matches_any_exact(n: str, names: set[str]) -> bool:
    """Strict equality match for upper-tier name lists. Substring matching here
    causes "Rome 2", "Rome 3" etc. to wrongly classify as 1000-tier."""
    return n in names


def categorize(
    tournament_name: str,
    tour: Tour,
    event_type: str | None = None,
) -> TournamentCategory:
    """Classify a tournament. `event_type` is the upstream type label
    ("Atp Singles", "Challenger Men Singles", "Itf Women Doubles", ...) and
    is the most reliable signal when present. Otherwise we fall back to
    name-pattern detection.
    """
    n = _norm(tournament_name)
    e = _norm(event_type or "")

    # 1. Most reliable signal: upstream event_type
    if "itf" in e:
        return TournamentCategory.ITF
    if "challenger" in e:
        return TournamentCategory.CHALLENGER

    # 2. Lower-tier from name patterns. Run BEFORE upper-tier matching so
    #    "ITF W75 Rome" doesn't bleed into 1000s through the city name.
    lower = _is_lower_tier_by_name(n)
    if lower is not None:
        return lower

    # 3. Slams (substring is fine — slam names don't appear in lower-tier names)
    if any(slam in n for slam in GRAND_SLAMS):
        return TournamentCategory.GRAND_SLAM

    if any(p in n for p in DAVIS_CUP_PATTERNS):
        return TournamentCategory.DAVIS_CUP
    if any(p in n for p in BJK_CUP_PATTERNS):
        return TournamentCategory.BJK_CUP

    if tour == Tour.ATP and _matches_any_exact(n, ATP_FINALS_NAMES):
        return TournamentCategory.ATP_FINALS
    if tour == Tour.WTA and _matches_any_exact(n, WTA_FINALS_NAMES):
        return TournamentCategory.WTA_FINALS

    # 4. 1000s / 500s — exact-match only. Anything that's "Rome 2" or "Madrid 3"
    #    falls through to default 250 (or below).
    if tour == Tour.ATP and _matches_any_exact(n, ATP_1000_NAMES):
        return TournamentCategory.ATP_1000
    if tour == Tour.WTA and _matches_any_exact(n, WTA_1000_NAMES):
        return TournamentCategory.WTA_1000

    if tour == Tour.ATP and _matches_any_exact(n, ATP_500_NAMES):
        return TournamentCategory.ATP_500
    if tour == Tour.WTA and _matches_any_exact(n, WTA_500_NAMES):
        return TournamentCategory.WTA_500

    if tour == Tour.ATP:
        return TournamentCategory.ATP_250
    if tour == Tour.WTA:
        return TournamentCategory.WTA_250

    return TournamentCategory.OTHER


# Sort weight for index pages — lowest first
_TIER_ORDER: dict[TournamentCategory, int] = {
    TournamentCategory.GRAND_SLAM: 0,
    TournamentCategory.ATP_FINALS: 1,
    TournamentCategory.WTA_FINALS: 1,
    TournamentCategory.ATP_1000: 2,
    TournamentCategory.WTA_1000: 2,
    TournamentCategory.ATP_500: 3,
    TournamentCategory.WTA_500: 3,
    TournamentCategory.ATP_250: 4,
    TournamentCategory.WTA_250: 4,
    TournamentCategory.DAVIS_CUP: 5,
    TournamentCategory.BJK_CUP: 5,
    TournamentCategory.CHALLENGER: 6,
    TournamentCategory.ITF: 7,
    TournamentCategory.OTHER: 8,
}


def tier_weight(c: TournamentCategory) -> int:
    return _TIER_ORDER.get(c, 99)


def recategorize_all(session) -> int:  # noqa: ANN001 — Session import would cycle
    """One-shot: re-classify every Tournament row using current heuristics.

    Useful after rolling out tweaks to the classifier. Called once per process
    on the rankings-sync boot path so it picks up any missed reclassifications.
    """
    from sqlmodel import select

    from app.models.tournament import Tournament

    changed = 0
    for t in session.exec(select(Tournament)).all():
        new_cat = categorize(t.name, t.tour)
        if t.category != new_cat:
            t.category = new_cat
            session.add(t)
            changed += 1
    if changed:
        session.commit()
    return changed
