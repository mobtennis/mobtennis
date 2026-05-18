"""Static Wikipedia title → internal player slug overrides.

The default resolution path is `slugify(wikilink_title)` minus
disambiguators like "(tennis)". That handles ~95% of cases. This table
catches the rest: spelling differences between Wikipedia's canonical
title and the way api-tennis / Sackmann named the player in our DB.

How to grow this table:
  Run apply_wiki_bracket.py against a tournament; unresolved players
  are printed at the end. For each, find the player in our DB (usually
  by full name search) and add a `"Wikipedia Title": "our-slug"` line.

Keep entries alphabetised within the file for diff-friendliness.
"""

WIKI_TITLE_TO_SLUG: dict[str, str] = {
    # Bootstrapped from Rome 2026 + FO 2025 + Halle 2025 parse runs.
    # Add entries here as the apply CLI surfaces them.
    #
    # These are players whose row in our DB has the surname/given-name
    # tokens in a different order than the Wikipedia canonical title.
    # Usually because Sackmann or api-tennis labelled the row with a
    # full-name string that put surnames first ("Martin Etcheverry Tomas"
    # rather than "Tomás Martín Etcheverry"). The slug, derived from
    # that string, doesn't match anything _candidate_slugs() generates
    # from the Wikipedia title.
    "Daniel Mérida":              "daniel-merida-aguilar",
    "Román Andrés Burruchaga":    "andres-burruchaga-roman",
    "Tomás Martín Etcheverry":    "martin-etcheverry-tomas",
    # Compound first-name with hyphen — Sackmann split the hyphenated
    # given name into two surnames in the wrong order.
    "Elena-Gabriela Ruse":        "gabriela-ruse-elena",
}
