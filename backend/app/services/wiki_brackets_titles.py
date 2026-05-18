"""Tournament-brand → Wikipedia page-title resolution.

Lifted out of the legacy draws_wikipedia.py so the new pipeline doesn't
import any of its parsing internals. Same data; the only logic here is
gluing the brand name + year + tour into the canonical Wikipedia title
format ("{year} {Brand} – {gender} singles").
"""

from __future__ import annotations

from app.models.player import Tour
from app.models.tournament import Tournament, TournamentCategory


# Slug (our internal) → Wikipedia article name (without year/draw suffix).
SLUG_TO_WIKI_NAME: dict[str, str] = {
    # Slams
    "australian-open": "Australian Open",
    "french-open": "French Open",
    "roland-garros": "French Open",
    "wimbledon": "Wimbledon Championships",
    "us-open": "US Open",
    # ATP/WTA 1000
    "indian-wells": "Indian Wells Open",
    "miami": "Miami Open",
    "monte-carlo": "Monte-Carlo Masters",
    "madrid": "Mutua Madrid Open",
    "rome": "Italian Open",
    "canada": "Canadian Open",
    "toronto": "Canadian Open",
    "montreal": "Canadian Open",
    "cincinnati": "Cincinnati Open",
    "shanghai": "Shanghai Masters",
    "paris": "Paris Masters",
    "doha": "Qatar Open",
    "dubai": "Dubai Tennis Championships",
    # ATP/WTA Finals
    "atp-finals": "ATP Finals",
    "wta-finals": "WTA Finals",
    # ATP/WTA 500 (growing set as we verify each)
    "hamburg": "Hamburg Open",
}


# Tournament categories the new pipeline supports. Sub-1000 events use
# section template variants we haven't audited end-to-end; expand this
# set as additional shapes get verified.
SCRAPABLE_CATEGORIES = {
    TournamentCategory.GRAND_SLAM,
    TournamentCategory.ATP_1000,
    TournamentCategory.WTA_1000,
    TournamentCategory.ATP_FINALS,
    TournamentCategory.WTA_FINALS,
    # ATP/WTA 500: only the events with an entry in SLUG_TO_WIKI_NAME
    # actually get scraped (wiki_title_for returns None otherwise), so
    # opening the gate here is safe — it doesn't try to scrape every
    # 500 indiscriminately.
    TournamentCategory.ATP_500,
    TournamentCategory.WTA_500,
}


def wiki_title_for(t: Tournament) -> str | None:
    """Compose the Wikipedia page title for a tournament's singles draw,
    or None if we don't have a mapping for this brand.

    Doubles is not in scope for the new pipeline; the legacy scraper
    used to do both via a `doubles` argument.
    """
    name = SLUG_TO_WIKI_NAME.get(t.slug)
    if not name:
        return None
    gender = "Men's" if t.tour == Tour.ATP else "Women's"
    # Wikipedia uses the en-dash (U+2013) between brand and draw kind.
    return f"{t.year} {name} – {gender} singles"
