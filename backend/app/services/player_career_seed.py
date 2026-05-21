"""Static career-high ranking seed for top players.

`Player.career_high_rank` is currently derived from the rankings sync —
each weekly snapshot updates it if the player's rank that week is the
best we've seen. That works going forward, but for players whose
historical peak predates our first ranking snapshot, the stored value
is wrong: e.g. Novak Djokovic shows #4 because that's the lowest rank
he's hit since we started syncing, but his actual career high is #1
(held for ~7 years total).

This module hard-codes the verified career-high singles ranking for
the top tier of active players. `apply_seed()` updates a Player row
ONLY when the seed value is better (lower number) than the stored
value — so it can't ever make data worse than the live-derived one.

How to extend:
  - Add a row to ATP_SEED / WTA_SEED with `{slug: career_high}`.
  - Source: ATPTour.com / WTATennis.com player profile (the "Career
    High" stat is published verbatim on each profile).
  - Slug is our internal slug (see `Player.slug`); the comment beside
    each entry shows the player's name for grep-ability.

Longer-term fix (not in this seed): pull career-high from Wikidata
via the players_bio_enrich job (P5985 — ATP highest singles ranking,
P5986 — WTA highest singles ranking). Once that's wired, this seed
becomes a small overlay for players whose Wikidata entry is stale or
missing the property.
"""

from __future__ import annotations

import logging

from sqlmodel import Session, select

from app.models.player import Player

log = logging.getLogger(__name__)


# ATP — verified career-high singles ranks from atptour.com player profiles.
ATP_SEED: dict[str, int] = {
    "novak-djokovic":              1,    # 7 years, total weeks: 428
    "jannik-sinner":               1,
    "carlos-alcaraz":              1,
    "daniil-medvedev":             1,
    "alexander-zverev":            2,
    "casper-ruud":                 2,
    "andrey-rublev":               5,
    "taylor-fritz":                4,
    "alex-de-minaur":              5,
    "ben-shelton":                 6,
    "felix-auger-aliassime":       6,
    "lorenzo-musetti":             6,
    "alexander-bublik":            17,
    "flavio-cobolli":              19,
    "jiri-lehecka":                21,
    "karen-khachanov":             8,
    "frances-tiafoe":              10,
    "cameron-norrie":              8,
    "alejandro-davidovich-fokina": 21,
    "tommy-paul":                  9,
    "francisco-cerundolo":         18,
    "jakub-mensik":                17,
    "joao-fonseca":                30,
    "tallon-griekspoor":           23,
    "corentin-moutet":             40,
    "brandon-nakashima":           33,
    "ugo-humbert":                 13,
    "denis-shapovalov":            10,
    "rafael-nadal":                1,
    "stefanos-tsitsipas":          3,
    "matteo-berrettini":           6,
    "hubert-hurkacz":              6,
    "grigor-dimitrov":             3,
    "gael-monfils":                6,
    "milos-raonic":                3,
    "stan-wawrinka":               3,
    "andy-murray":                 1,
    "diego-schwartzman":           8,
    "kei-nishikori":               4,
    "marin-cilic":                 3,
    "kevin-anderson":              5,
    "david-goffin":                7,
    "richard-gasquet":             7,
}


# WTA — verified career-high singles ranks from wtatennis.com profiles.
WTA_SEED: dict[str, int] = {
    "aryna-sabalenka":      1,
    "iga-swiatek":          1,
    "coco-gauff":           2,
    "jessica-pegula":       3,
    "elena-rybakina":       3,
    "elina-svitolina":      3,
    "naomi-osaka":          1,
    "madison-keys":         5,
    "amanda-anisimova":     4,
    "karolina-muchova":     8,
    "belinda-bencic":       4,
    "mirra-andreeva":       5,
    "marta-kostyuk":        13,
    "ekaterina-alexandrova": 11,
    "victoria-mboko":       9,
    "jasmine-paolini":      4,
    "linda-noskova":        16,
    "sorana-cirstea":       21,
    "anna-kalinskaya":      11,
    "leylah-fernandez":     13,
    "diana-shnaider":       12,
    "elise-mertens":        12,
    "emma-raducanu":        10,
    "iva-jovic":            32,
    "liudmila-samsonova":   12,
    "clara-tauson":         21,
    "marie-bouzkova":       25,
    "petra-kvitova":        2,
    "simona-halep":         1,
    "garbine-muguruza":     1,
    "angelique-kerber":     1,
    "venus-williams":       1,
    "serena-williams":      1,
    "caroline-wozniacki":   1,
    "victoria-azarenka":    1,
    "ons-jabeur":           2,
    "barbora-krejcikova":   2,
    "emma-navarro":         8,
    "qinwen-zheng":         5,
    "danielle-collins":     7,
}


def apply_seed(session: Session) -> dict:
    """Walk the seed and update Player rows where the seed is more
    authoritative. Returns a summary dict."""
    updated = 0
    skipped_better = 0
    missing = 0

    for tour_label, seed in (("atp", ATP_SEED), ("wta", WTA_SEED)):
        for slug, career_high in seed.items():
            p = session.exec(select(Player).where(Player.slug == slug)).first()
            if not p:
                missing += 1
                continue
            current = p.career_high_rank
            if current is not None and current <= career_high:
                # We already have a better (= lower) value. Either the
                # live sync caught the player at a higher peak, or another
                # source landed first. Don't downgrade.
                skipped_better += 1
                continue
            log.info(
                "%s: career_high_rank %s → %s (%s)",
                slug, current, career_high, tour_label,
            )
            p.career_high_rank = career_high
            session.add(p)
            updated += 1

    session.commit()
    return {
        "updated": updated,
        "skipped_already_better": skipped_better,
        "missing_players": missing,
    }
