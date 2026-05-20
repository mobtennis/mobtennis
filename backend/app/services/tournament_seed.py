"""Static metadata seed for the top tournament brands.

The auto-enrichment via Wikipedia + Wikidata is patchy — many rows in
the catalog still have NULL `city`, `country_code`, `draw_size`,
`prize_money`, and `wikipedia_url`. For the brands that matter most
(the four Slams, the nine ATP 1000s, the ten WTA 1000s, and the two
year-end Finals) we hand-curate a small data table here so the
per-brand page looks credible the moment it loads.

The seed only fills NULL columns — it never overwrites enrichment that
already landed. Re-running is safe.

Each entry covers BOTH tours of a co-staged event (Madrid, Indian
Wells, Miami, Cincinnati …) since the city, country, and Wikipedia
article are the same for both. Per-tour fields (draw_size,
prize_money) accept a dict keyed by 'atp' / 'wta'.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from sqlmodel import Session, select

from app.models.tournament import Tournament

log = logging.getLogger(__name__)


@dataclass
class _BrandSeed:
    """Per-brand metadata. Per-tour numeric fields use {'atp': N, 'wta': N};
    a single int means the same value for both tours."""
    slug: str
    city: str | None
    country_code: str | None
    wikipedia_url: str | None
    description: str | None = None
    # Draw sizes (singles main draw).
    draw_size: int | dict[str, int] | None = None
    # Annualised prize pool in USD; rough recent figures (last public
    # edition). Single int = same for both tours.
    prize_money: int | dict[str, int] | None = None
    # Typical start (month, day) — used to fill `start_date` when the
    # row has none. Sets to the current year's instance of that date.
    typical_start: tuple[int, int] | None = None
    typical_end: tuple[int, int] | None = None


SEEDS: list[_BrandSeed] = [
    # ---- Grand Slams ----
    _BrandSeed(
        slug="australian-open",
        city="Melbourne", country_code="AUS",
        wikipedia_url="https://en.wikipedia.org/wiki/Australian_Open",
        description=(
            "The Australian Open is the first of the four Grand Slam "
            "tournaments of the tennis calendar, held annually in Melbourne, "
            "Australia. First held in 1905, it is played on outdoor hard "
            "courts at Melbourne Park."
        ),
        draw_size=128,
        prize_money=58_500_000,
        typical_start=(1, 13), typical_end=(1, 26),
    ),
    _BrandSeed(
        slug="roland-garros",
        city="Paris", country_code="FRA",
        wikipedia_url="https://en.wikipedia.org/wiki/French_Open",
        description=(
            "The French Open, also known as Roland-Garros, is a Grand Slam "
            "tennis tournament held over two weeks in late May and early "
            "June at the Stade Roland Garros in Paris, France. It is the "
            "premier clay-court championship event in the world and the "
            "only Grand Slam tournament played on clay."
        ),
        draw_size=128,
        prize_money=53_500_000,
        typical_start=(5, 25), typical_end=(6, 8),
    ),
    _BrandSeed(
        slug="wimbledon",
        city="London", country_code="GBR",
        wikipedia_url="https://en.wikipedia.org/wiki/Wimbledon_Championships",
        description=(
            "The Wimbledon Championships is the oldest tennis tournament in "
            "the world and is widely regarded as the most prestigious. It "
            "has been held at the All England Club in Wimbledon, London, "
            "since 1877 and is played on outdoor grass courts."
        ),
        draw_size=128,
        prize_money=50_000_000,
        typical_start=(6, 30), typical_end=(7, 13),
    ),
    _BrandSeed(
        slug="us-open",
        city="New York", country_code="USA",
        wikipedia_url="https://en.wikipedia.org/wiki/US_Open_(tennis)",
        description=(
            "The US Open is the modern version of one of the oldest tennis "
            "championships in the world, the U.S. National Championship. "
            "Held annually since 1881 in New York City, it is the fourth "
            "and final Grand Slam of the calendar year, played on outdoor "
            "hard courts at the USTA Billie Jean King National Tennis Center."
        ),
        draw_size=128,
        prize_money=75_000_000,
        typical_start=(8, 25), typical_end=(9, 8),
    ),

    # ---- ATP 1000s + WTA 1000s (co-staged where applicable) ----
    _BrandSeed(
        slug="indian-wells",
        city="Indian Wells", country_code="USA",
        wikipedia_url="https://en.wikipedia.org/wiki/Indian_Wells_Masters",
        description=(
            "The Indian Wells Open is a tennis tournament held annually in "
            "March at the Indian Wells Tennis Garden in Indian Wells, "
            "California. It is the largest tennis tournament outside of "
            "the Grand Slams in terms of attendance, played on outdoor "
            "hard courts."
        ),
        draw_size=96,
        typical_start=(3, 4), typical_end=(3, 17),
    ),
    _BrandSeed(
        slug="miami",
        city="Miami Gardens", country_code="USA",
        wikipedia_url="https://en.wikipedia.org/wiki/Miami_Open_(tennis)",
        description=(
            "The Miami Open is a tennis tournament held annually in March "
            "at Hard Rock Stadium in Miami Gardens, Florida. Established "
            "in 1985, it is one of the largest combined ATP and WTA events "
            "outside the Grand Slams, played on outdoor hard courts."
        ),
        draw_size=96,
        typical_start=(3, 18), typical_end=(3, 31),
    ),
    _BrandSeed(
        slug="monte-carlo",
        city="Monte Carlo", country_code="MCO",
        wikipedia_url="https://en.wikipedia.org/wiki/Monte-Carlo_Masters",
        description=(
            "The Monte-Carlo Masters is an annual men's tennis tournament "
            "held at the Monte-Carlo Country Club in Roquebrune-Cap-Martin, "
            "France. First held in 1897, it kicks off the European clay-"
            "court season."
        ),
        draw_size={"atp": 56},
        typical_start=(4, 5), typical_end=(4, 13),
    ),
    _BrandSeed(
        slug="madrid",
        city="Madrid", country_code="ESP",
        wikipedia_url="https://en.wikipedia.org/wiki/Madrid_Open_(tennis)",
        description=(
            "The Madrid Open is a tennis tournament held annually in early "
            "May at the Caja Mágica in Madrid, Spain. Founded in 2002, the "
            "combined ATP and WTA event is played on outdoor clay courts."
        ),
        draw_size=96,
        typical_start=(4, 22), typical_end=(5, 5),
    ),
    _BrandSeed(
        slug="rome",
        city="Rome", country_code="ITA",
        wikipedia_url="https://en.wikipedia.org/wiki/Italian_Open_(tennis)",
        description=(
            "The Italian Open, also known as the Internazionali BNL d'Italia, "
            "is a clay-court tennis tournament held annually at the Foro "
            "Italico in Rome, Italy. First held in 1930, it is one of the "
            "oldest and most prestigious clay-court events on the tennis "
            "calendar, played in the lead-up to the French Open."
        ),
        draw_size=96,
        typical_start=(5, 6), typical_end=(5, 18),
    ),
    _BrandSeed(
        slug="canadian-open",
        city="Toronto / Montreal", country_code="CAN",
        wikipedia_url="https://en.wikipedia.org/wiki/Canadian_Open_(tennis)",
        description=(
            "The Canadian Open is an annual tennis tournament held in "
            "Canada, alternating each year between Toronto and Montreal. "
            "First held in 1881, it is one of the oldest tennis tournaments "
            "in the world."
        ),
        draw_size=96,
        typical_start=(8, 4), typical_end=(8, 17),
    ),
    _BrandSeed(
        slug="cincinnati",
        city="Cincinnati", country_code="USA",
        wikipedia_url="https://en.wikipedia.org/wiki/Cincinnati_Open",
        description=(
            "The Cincinnati Open is an annual tennis tournament held at the "
            "Lindner Family Tennis Center in Mason, Ohio, near Cincinnati. "
            "First held in 1899, it is one of the oldest tennis tournaments "
            "in the United States, played on outdoor hard courts."
        ),
        draw_size=96,
        typical_start=(8, 11), typical_end=(8, 24),
    ),
    _BrandSeed(
        slug="shanghai",
        city="Shanghai", country_code="CHN",
        wikipedia_url="https://en.wikipedia.org/wiki/Shanghai_Masters_(tennis)",
        description=(
            "The Shanghai Masters is a men's professional tennis tournament "
            "held annually in Shanghai, China at the Qizhong Forest Sports "
            "City Arena. Established in 2009, it is the only Masters 1000 "
            "event held in Asia, played on outdoor hard courts."
        ),
        draw_size={"atp": 96},
        typical_start=(10, 1), typical_end=(10, 14),
    ),
    _BrandSeed(
        slug="paris-bercy",
        city="Paris", country_code="FRA",
        wikipedia_url="https://en.wikipedia.org/wiki/Paris_Masters",
        description=(
            "The Paris Masters is a men's tennis tournament held annually "
            "at the Accor Arena in Paris, France. First held in 1968, it "
            "is the last Masters 1000 event of the ATP Tour calendar, "
            "played on indoor hard courts in late October or early November."
        ),
        draw_size={"atp": 56},
        typical_start=(10, 27), typical_end=(11, 2),
    ),

    # WTA-only 1000s not co-staged with an ATP 1000.
    _BrandSeed(
        slug="dubai",
        city="Dubai", country_code="ARE",
        wikipedia_url="https://en.wikipedia.org/wiki/Dubai_Tennis_Championships",
        description=(
            "The Dubai Tennis Championships is a tennis tournament held "
            "annually in Dubai, United Arab Emirates. The WTA event is a "
            "1000-level tournament; the ATP event is a 500-level "
            "tournament. Both are played on outdoor hard courts."
        ),
        draw_size={"wta": 56},
        typical_start=(2, 16), typical_end=(2, 22),
    ),
    _BrandSeed(
        slug="doha",
        city="Doha", country_code="QAT",
        wikipedia_url="https://en.wikipedia.org/wiki/Qatar_Open",
        description=(
            "The Qatar Open is a tennis tournament held annually at the "
            "Khalifa International Tennis and Squash Complex in Doha, "
            "Qatar. The WTA event is a 1000-level tournament; the ATP "
            "event is a 500-level tournament."
        ),
        draw_size={"wta": 56},
        typical_start=(2, 9), typical_end=(2, 15),
    ),
    _BrandSeed(
        slug="beijing",
        city="Beijing", country_code="CHN",
        wikipedia_url="https://en.wikipedia.org/wiki/China_Open_(tennis)",
        description=(
            "The China Open is a tennis tournament held annually at the "
            "National Tennis Center in Beijing, China. The WTA event is a "
            "1000-level tournament; the ATP event is a 500-level tournament. "
            "Both are played on outdoor hard courts."
        ),
        draw_size={"wta": 64},
        typical_start=(9, 24), typical_end=(10, 5),
    ),
    _BrandSeed(
        slug="wuhan",
        city="Wuhan", country_code="CHN",
        wikipedia_url="https://en.wikipedia.org/wiki/Wuhan_Open",
        description=(
            "The Wuhan Open is a WTA Premier tournament played annually on "
            "outdoor hard courts in Wuhan, China. It is one of the WTA's "
            "1000-level events, held in late September or early October."
        ),
        draw_size={"wta": 56},
        typical_start=(10, 6), typical_end=(10, 12),
    ),

    # ---- Year-end Finals ----
    _BrandSeed(
        slug="atp-finals",
        city="Turin", country_code="ITA",
        wikipedia_url="https://en.wikipedia.org/wiki/ATP_Finals",
        description=(
            "The ATP Finals is the season-ending men's tennis tournament "
            "featuring the eight highest-ranked singles players and the "
            "eight highest-ranked doubles teams in the world. Played on "
            "indoor hard courts, it is the second-most prestigious men's "
            "tennis tournament after the four Grand Slam tournaments."
        ),
        draw_size={"atp": 8},
        typical_start=(11, 9), typical_end=(11, 16),
    ),
    _BrandSeed(
        slug="wta-finals",
        city="Riyadh", country_code="SAU",
        wikipedia_url="https://en.wikipedia.org/wiki/WTA_Finals",
        description=(
            "The WTA Finals is the season-ending women's tennis tournament "
            "featuring the eight highest-ranked singles players and the "
            "eight highest-ranked doubles teams of the WTA Tour."
        ),
        draw_size={"wta": 8},
        typical_start=(11, 1), typical_end=(11, 8),
    ),
]


def _per_tour(value, tour: str) -> int | None:
    """Resolve a per-tour field. `value` is int, dict, or None."""
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get(tour)
    return int(value)


def apply_seeds(session: Session, *, year: int | None = None) -> dict:
    """Fill NULL columns on Tournament rows matching the seed table.

    By default applies to every year present in the catalog. If `year`
    is given, only rows for that year are touched (useful for boot-time
    enrichment of the current year).

    Only NULL columns are updated — existing values from prior
    enrichment runs are never overwritten.
    """
    updated_rows = 0
    fields_set = 0

    for seed in SEEDS:
        q = select(Tournament).where(Tournament.slug == seed.slug)
        if year is not None:
            q = q.where(Tournament.year == year)
        rows = session.exec(q).all()
        for r in rows:
            row_changed = False
            tour_value = r.tour.value if hasattr(r.tour, "value") else str(r.tour)
            new = {
                "city": seed.city,
                "country_code": seed.country_code,
                "wikipedia_url": seed.wikipedia_url,
                "description": seed.description,
                "draw_size": _per_tour(seed.draw_size, tour_value),
                "prize_money": _per_tour(seed.prize_money, tour_value),
            }
            if seed.typical_start:
                new["start_date"] = date(r.year, *seed.typical_start)
            if seed.typical_end:
                new["end_date"] = date(r.year, *seed.typical_end)

            for field, value in new.items():
                if value is None:
                    continue
                if getattr(r, field, None) is None:
                    setattr(r, field, value)
                    row_changed = True
                    fields_set += 1
            if row_changed:
                session.add(r)
                updated_rows += 1

    session.commit()
    return {"rows_updated": updated_rows, "fields_set": fields_set}
