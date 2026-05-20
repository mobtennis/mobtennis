"""Surface suspected brand-slug collisions for human review.

Three ingest sources name the same tournament differently:
  - Sackmann CSVs (historical) — what tennis_atp/tennis_wta call the brand
  - api-tennis (live feed)    — marketing / English names
  - Wikipedia (enrichment)    — canonical encyclopedic title

When two of those name a brand differently, our catalog ends up with
two slug rows for the same event and the per-brand page shows half
the story. The /tournaments/atp/french-open vs /atp/roland-garros
collision was found by hand; this script automates the search.

It cross-references all three signals and outputs candidate clusters
ranked by confidence. The script does NOT mutate the DB — the
operator reviews the report and decides which clusters become entries
in `BRAND_ALIASES` (see app/services/tournament_resolver.py), then
runs `scripts/merge_tournament_aliases.py` to consolidate.

Signals, in order of strength:
  S1. SAME wikipedia_url across slugs                — very strong
  S2. SAME tournament name across slugs              — very strong
  S3. SAME (tour, category, surface, typical-month)  — moderate;
       used only as a *bucket* for filtering, not a positive signal
       on its own (lots of unrelated 250s share the bucket).
  S4. SHARED champion across years between slugs     — strong
  S5. SLUG Levenshtein-near-1                        — weak; only
       informative once another signal already fires.

Usage:
  uv run python -m scripts.find_tournament_collisions
  uv run python -m scripts.find_tournament_collisions --min-rows 2
  uv run python -m scripts.find_tournament_collisions --category atp_1000
"""

from __future__ import annotations

import argparse
import logging
from collections import defaultdict
from dataclasses import dataclass, field

from sqlmodel import Session, select

from app.db.session import engine, init_db
from app.models.match import Match
from app.models.tournament import Tournament

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("collisions")


@dataclass
class BrandFingerprint:
    slug: str
    rows: int                          # number of (year, tour) instances
    tours: set[str]
    categories: set[str]
    surfaces: set[str]
    months: set[int]
    years: set[int]
    wikipedia_urls: set[str]
    names: set[str]
    cities: set[str]
    champion_ids: set[int] = field(default_factory=set)


def _normalise_name(name: str) -> str:
    """Loose name match: lowercase, strip ATP/WTA/Masters/Open/Cup suffixes."""
    s = name.lower().strip()
    for trim in (
        "atp ", "wta ", " atp", " wta",
        " masters", " open", " international",
        " championship", " championships",
        " 1000", " 500", " 250",
        " mens", " womens",
    ):
        s = s.replace(trim, "")
    return " ".join(s.split())


def _build_fingerprints(session: Session) -> dict[str, BrandFingerprint]:
    fps: dict[str, BrandFingerprint] = {}
    rows = session.exec(
        select(
            Tournament.id, Tournament.slug, Tournament.year, Tournament.tour,
            Tournament.category, Tournament.surface, Tournament.start_date,
            Tournament.wikipedia_url, Tournament.name, Tournament.city,
        )
    ).all()
    for r in rows:
        fp = fps.setdefault(r.slug, BrandFingerprint(
            slug=r.slug, rows=0,
            tours=set(), categories=set(), surfaces=set(),
            months=set(), years=set(),
            wikipedia_urls=set(), names=set(), cities=set(),
        ))
        fp.rows += 1
        fp.tours.add(r.tour.value if hasattr(r.tour, "value") else str(r.tour))
        if r.category:
            fp.categories.add(r.category.value if hasattr(r.category, "value") else str(r.category))
        if r.surface:
            fp.surfaces.add(r.surface)
        if r.start_date:
            fp.months.add(r.start_date.month)
        fp.years.add(r.year)
        if r.wikipedia_url:
            fp.wikipedia_urls.add(r.wikipedia_url)
        if r.name:
            fp.names.add(_normalise_name(r.name))
        if r.city:
            fp.cities.add(r.city.lower().strip())

    # Champions per slug — used as a cross-signal. One query for all.
    champ_rows = session.exec(
        select(Tournament.slug, Match.winner_id)
        .join(Match, Match.tournament_id == Tournament.id)
        .where(Match.round.in_(["F"]), Match.winner_id.is_not(None), Match.is_doubles == False)  # noqa: E712
    ).all()
    for slug, winner_id in champ_rows:
        if slug in fps and winner_id is not None:
            fps[slug].champion_ids.add(winner_id)
    return fps


def _report_by_wiki(fps: dict[str, BrandFingerprint], *, limit: int) -> None:
    """Cluster slugs by shared Wikipedia URL.

    Drops the data-driven noise URLs (already wiped from fingerprints)
    so what's left is mostly genuine "two slugs for the same brand"
    candidates. Operator reviews and decides which become aliases.
    """
    by_url: dict[str, list[BrandFingerprint]] = defaultdict(list)
    for fp in fps.values():
        for u in fp.wikipedia_urls:
            by_url[u].append(fp)

    # Tournament-looking URLs only — filter out player pages, season
    # indices, list articles. These tokens are stable in en.wikipedia
    # tournament article titles.
    def _tournament_url(url: str) -> bool:
        lo = url.lower()
        return any(t in lo for t in (
            "_open_", "_masters", "_championships", "_grand_prix",
            "_classic", "_international", "_trophy", "_finals", "_cup",
            "open_(tennis)", "italian_open", "french_open", "us_open",
            "wimbledon", "australian_open", "atp_finals", "wta_finals",
        ))

    clusters = [
        (url, sorted({fp.slug for fp in hits}))
        for url, hits in by_url.items()
        if len({fp.slug for fp in hits}) >= 2 and _tournament_url(url)
    ]
    clusters.sort(key=lambda x: (-len(x[1]), x[0]))

    log.info("=" * 78)
    log.info(f"By-Wikipedia clusters — {len(clusters)} tournament URL(s) "
             f"referenced by ≥2 slugs.")
    log.info("=" * 78)
    log.info("")
    for url, slugs in clusters[:limit]:
        log.info(f"  {url}")
        log.info(f"    {len(slugs)} slugs: {slugs}")
        # Suggest canonical = the slug with the most rows.
        canonical = max(slugs, key=lambda s: fps[s].rows)
        aliases = [s for s in slugs if s != canonical]
        log.info(f"    suggested:  \"{canonical}\":  {{{', '.join(f'\"{a}\"' for a in aliases)}}}")
        log.info("")


@dataclass
class Suspect:
    a: str
    b: str
    score: float
    reasons: list[str]


def _score_pair(a: BrandFingerprint, b: BrandFingerprint) -> Suspect | None:
    reasons: list[str] = []
    score = 0.0

    # Wikipedia overlap, with known-false-positive blocklist. The
    # tournament enrichment job sometimes matched ITF-tier slugs to a
    # generic disambiguation / list page, which then shows up as a
    # shared URL across hundreds of unrelated events. Exclude those.
    # Heuristic noise filter: a Wikipedia URL shared between two slugs
    # is meaningful only if it isn't a generic tour/season/player page.
    # The tournament enrichment job sometimes resolves an unknown brand
    # to a tour-index article or a player's career page, which then
    # shows up as a shared URL across dozens of unrelated events.
    def _looks_like_noise(url: str) -> bool:
        u = url.lower()
        return (
            "list_of_" in u
            or "tour_finals" not in u and (
                "atp_tour" in u
                or "wta_tour" in u
                or "atp_challenger_tour" in u
                or "_tennis_season" in u
                or "career_statistics" in u
                or "wta_125_tournaments" in u
                or u.endswith("/tennis")
            )
        )
    wiki_overlap = {
        u for u in (a.wikipedia_urls & b.wikipedia_urls)
        if not _looks_like_noise(u)
    }
    if wiki_overlap:
        score += 5.0
        reasons.append(f"shared wikipedia_url ({sorted(wiki_overlap)[0]})")

    name_overlap = a.names & b.names
    if name_overlap:
        score += 4.0
        reasons.append(f"normalised name match ({sorted(name_overlap)[0]!r})")

    city_overlap = a.cities & b.cities
    month_overlap = a.months & b.months
    cat_overlap = a.categories & b.categories
    if city_overlap and month_overlap and cat_overlap:
        score += 3.0
        reasons.append(
            f"same city + month + tier ({sorted(city_overlap)[0]}, "
            f"month={sorted(month_overlap)[0]}, {sorted(cat_overlap)[0]})"
        )

    # Shared champions used to be in this scorer at 4 pts for ≥2 hits.
    # Removed: top players win across dozens of different events
    # ("Adelaide ↔ Wimbledon" both have Sinner + Djokovic finals across
    # years, but they're obviously not the same brand). Champion overlap
    # is informative only as a tie-breaker once name/wiki already fire.

    # Tour cohesion: both ATP, both WTA, or both co-staged.
    if not (a.tours & b.tours):
        # Slugs with disjoint tours are almost never the same brand.
        # Catches WTA-only events that happen to share a city with an
        # ATP-only one but aren't the same tournament.
        return None

    if score < 4.0:
        return None
    return Suspect(a=a.slug, b=b.slug, score=score, reasons=reasons)


def find_suspects(
    fps: dict[str, BrandFingerprint], *,
    min_rows: int,
    strict: bool = False,
) -> list[Suspect]:
    """Pairwise scan, restricted to slugs with at least `min_rows`
    instances each (single-row entries are usually noisy)."""
    keys = [s for s, fp in fps.items() if fp.rows >= min_rows]

    # Data-driven noise filter: a wikipedia_url shared across MORE than
    # 3 distinct brand slugs is almost certainly an enrichment-side bug
    # (matched to a tour index, a player career page, a list article).
    # Wipe those URLs from every fingerprint before scoring.
    url_to_slugs: dict[str, set[str]] = defaultdict(set)
    for slug, fp in fps.items():
        for u in fp.wikipedia_urls:
            url_to_slugs[u].add(slug)
    noisy_urls = {u for u, slugs in url_to_slugs.items() if len(slugs) > 3}
    if noisy_urls:
        log.info(
            f"(filtering {len(noisy_urls)} wikipedia URL(s) shared across "
            f">3 distinct slugs — likely enrichment noise)"
        )
        for fp in fps.values():
            fp.wikipedia_urls -= noisy_urls

    suspects: list[Suspect] = []
    for i, sa in enumerate(keys):
        a = fps[sa]
        # Indexing trick: only walk pairs once and skip slugs with no
        # cross-signal indexable to a, to avoid an O(N^2) full sweep on
        # 7000 slugs. We bucket by category first.
        for sb in keys[i + 1:]:
            b = fps[sb]
            # Cheap pre-filter — must share at least one tour, year,
            # AND category bucket OR a wikipedia_url OR a normalised name
            # (otherwise no signal can fire).
            if not (
                (a.wikipedia_urls & b.wikipedia_urls)
                or (a.names & b.names)
                or (a.categories & b.categories and a.cities & b.cities)
            ):
                continue
            s = _score_pair(a, b)
            if s:
                if strict and not any(
                    r.startswith(("shared wikipedia_url",
                                  "normalised name match"))
                    for r in s.reasons
                ):
                    continue
                suspects.append(s)
    suspects.sort(key=lambda s: (-s.score, s.a, s.b))
    return suspects


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--min-rows", type=int, default=2,
        help="Minimum number of (year, tour) rows per slug. Default 2.",
    )
    parser.add_argument(
        "--category", default=None,
        help="Filter both sides of each pair to a single category "
             "(grand_slam / atp_1000 / wta_1000 / etc).",
    )
    parser.add_argument(
        "--exclude-tiers", default="itf,challenger,other",
        help="Comma-separated list of categories to skip (case-insensitive). "
             "Default excludes the low-tier noise where enrichment is "
             "weakest.",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="Require a strong-evidence pair: at least one of "
             "(shared wikipedia_url, normalised name match). Recommended "
             "for headline-tier sweeps.",
    )
    parser.add_argument(
        "--by-wiki", action="store_true",
        help="Skip pairwise scoring; report clusters of slugs that "
             "share a tournament-looking Wikipedia URL. This is the "
             "highest-signal view of the catalog — what made it into "
             "BRAND_ALIASES so far was 90%% found this way.",
    )
    parser.add_argument(
        "--limit", type=int, default=100,
        help="Cap the report. Default 100.",
    )
    args = parser.parse_args()

    init_db()
    with Session(engine) as session:
        fps = _build_fingerprints(session)

    if args.category:
        fps = {
            slug: fp for slug, fp in fps.items()
            if args.category in fp.categories
        }

    excluded = {t.strip().lower() for t in args.exclude_tiers.split(",") if t.strip()}
    if excluded:
        fps = {
            slug: fp for slug, fp in fps.items()
            # A slug is kept iff at least ONE of its categories is not
            # in the exclude list. (A slug that's only ever ITF should
            # be dropped; one that's mostly ATP_1000 with a stray ITF
            # row shouldn't.)
            if (fp.categories - excluded)
        }

    if args.by_wiki:
        _report_by_wiki(fps, limit=args.limit)
        return

    suspects = find_suspects(fps, min_rows=args.min_rows, strict=args.strict)

    if not suspects:
        log.info("No suspects found.")
        return

    log.info("=" * 78)
    log.info("Tournament-slug collision suspects")
    log.info("=" * 78)
    log.info(
        f"{len(suspects)} candidate pair(s); showing top {min(len(suspects), args.limit)}."
    )
    log.info("Confidence score: 5 = wikipedia overlap, 4 = normalised name match,")
    log.info("                  3 = same city+month+tier, 4 = ≥2 shared champions.")
    log.info("")

    for s in suspects[: args.limit]:
        a, b = fps[s.a], fps[s.b]
        log.info(f"[{s.score:>4.1f}]  {s.a}  ↔  {s.b}")
        log.info(f"        a: {a.rows} rows, tours={sorted(a.tours)}, "
                 f"cat={sorted(a.categories)}, years=[{min(a.years)}…{max(a.years)}]")
        log.info(f"        b: {b.rows} rows, tours={sorted(b.tours)}, "
                 f"cat={sorted(b.categories)}, years=[{min(b.years)}…{max(b.years)}]")
        for r in s.reasons:
            log.info(f"        - {r}")
        # Suggested canonical = slug with more rows (more history).
        canonical, alias = (s.a, s.b) if a.rows >= b.rows else (s.b, s.a)
        log.info(f"        suggested: \"{canonical}\":  {{\"{alias}\"}}")
        log.info("")


if __name__ == "__main__":
    main()
