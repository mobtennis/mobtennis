"""Wikipedia-sourced singles-title records for Slams + Masters 1000s.

Sourced manually from each tournament's Wikipedia article on 2026-05-31.
Only records that could be cross-checked against Wikipedia's infobox or
champions list are included; tournaments where we couldn't get a clean
answer are deliberately absent so the API returns no records for them
(better silence than a wrong claim).

Why this exists at all: our own Match data via Sackmann starts in 1968,
which misses everything pre-Open-Era (Margaret Court's 11 Australian
Open titles, the early Wimbledons, US Open clay/grass-era champions).
Computing "Most titles" from our own data ships obviously-wrong answers
(Nadal at 5 RG titles instead of 14, because we'd missed editions).
This file is the canonical answer for the tournaments where we have it.

Update cadence: edit by hand when a record actually shifts. Slam
records change once every few years (Djokovic +1 at AO in 2023; Nadal
+1 at RG in 2022). Re-pulling all rows annually is plenty.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class WikipediaRecord:
    title: str
    """Display title, e.g. "Most singles titles"."""
    player_name: str
    """Full name. Used to look up the Player row for slug + image."""
    count: int
    """Number of titles. Rendered as e.g. "14 titles" / "1 title"."""
    tied_with: tuple[str, ...] = ()
    """Other players tied at the same count. Rendered in the detail field."""


# Keyed by (tour, slug) where tour is the lowercase Tour enum value.
TOURNAMENT_RECORDS: dict[tuple[str, str], tuple[WikipediaRecord, ...]] = {
    # ----- Grand Slams -----
    ("atp", "australian-open"): (
        WikipediaRecord("Most singles titles", "Novak Djokovic", 10),
    ),
    ("wta", "australian-open"): (
        WikipediaRecord("Most singles titles", "Margaret Court", 11),
    ),
    ("atp", "roland-garros"): (
        WikipediaRecord("Most singles titles", "Rafael Nadal", 14),
    ),
    ("wta", "roland-garros"): (
        WikipediaRecord("Most singles titles", "Chris Evert", 7),
    ),
    ("atp", "wimbledon"): (
        WikipediaRecord("Most singles titles", "Roger Federer", 8),
    ),
    ("wta", "wimbledon"): (
        WikipediaRecord("Most singles titles", "Martina Navratilova", 9),
    ),
    ("atp", "us-open"): (
        WikipediaRecord(
            "Most singles titles (Open Era)", "Roger Federer", 5,
            tied_with=("Jimmy Connors", "Pete Sampras"),
        ),
    ),
    ("wta", "us-open"): (
        WikipediaRecord(
            "Most singles titles (Open Era)", "Serena Williams", 6,
            tied_with=("Chris Evert",),
        ),
    ),

    # ----- ATP Masters 1000 -----
    ("atp", "indian-wells"): (
        WikipediaRecord("Most singles titles", "Roger Federer", 5),
    ),
    ("atp", "miami"): (
        WikipediaRecord("Most singles titles", "Andre Agassi", 6),
    ),
    ("atp", "monte-carlo"): (
        WikipediaRecord("Most singles titles", "Rafael Nadal", 11),
    ),
    ("atp", "madrid"): (
        WikipediaRecord("Most singles titles", "Rafael Nadal", 5),
    ),
    ("atp", "rome"): (
        WikipediaRecord("Most singles titles (Open Era)", "Rafael Nadal", 10),
    ),
    # Canadian Open alternates between Toronto and Montreal. Wikipedia treats
    # it as one tournament with one record list; our DB splits the slugs by
    # host city, so the same record card lives under both keys.
    ("atp", "toronto"): (
        WikipediaRecord("Most singles titles (Open Era)", "Ivan Lendl", 6),
    ),
    ("atp", "montreal"): (
        WikipediaRecord("Most singles titles (Open Era)", "Ivan Lendl", 6),
    ),
    ("atp", "cincinnati"): (
        WikipediaRecord("Most singles titles (Open Era)", "Roger Federer", 7),
    ),
    ("atp", "shanghai"): (
        WikipediaRecord("Most singles titles", "Novak Djokovic", 4),
    ),
    ("atp", "paris"): (
        WikipediaRecord("Most singles titles", "Novak Djokovic", 7),
    ),

    # ----- WTA 1000 (only events where Wikipedia gave a clean answer) -----
    # Skipped: indian-wells (records section ambiguous in the article),
    # toronto/montreal (women's table truncated in fetch), cincinnati
    # (same), dubai (Wikipedia listed conflicting counts), beijing
    # (uncertain leader), shanghai/paris/guadalajara (new events with
    # too few editions to have a Wikipedia-summarized record).
    ("wta", "miami"): (
        WikipediaRecord("Most singles titles", "Serena Williams", 8),
    ),
    ("wta", "madrid"): (
        WikipediaRecord(
            "Most singles titles", "Aryna Sabalenka", 3,
            tied_with=("Petra Kvitova",),
        ),
    ),
    ("wta", "rome"): (
        # Our Player table stores names without diacritics; the tied/lookup
        # paths both rely on exact match, so the spelling here matches the
        # DB row, not the Wikipedia headline.
        WikipediaRecord("Most singles titles (Open Era)", "Conchita Martinez", 4),
    ),
    ("wta", "wuhan"): (
        WikipediaRecord("Most singles titles", "Aryna Sabalenka", 3),
    ),
    ("wta", "doha"): (
        WikipediaRecord(
            "Most singles titles", "Iga Swiatek", 3,
            tied_with=("Victoria Azarenka",),
        ),
    ),
}


def get_records(tour: str, slug: str) -> tuple[WikipediaRecord, ...]:
    """Return curated records for this (tour, slug), or empty tuple."""
    return TOURNAMENT_RECORDS.get((tour, slug), ())
