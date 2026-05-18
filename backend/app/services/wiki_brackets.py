"""Wikipedia tournament bracket parser (Phase 1 + 1.5 of the new pipeline).

Pure functions only — given a tournament's Wikipedia page wikitext, returns
a structured intermediate model of every match described on the page. No DB
access here; reconciliation with our Match rows happens in a separate module
that consumes this output.

Why a clean rewrite:
  The previous implementation tried to handle bracket-position math at the
  same time as wikitext parsing, made a number of structural assumptions that
  broke on Masters 1000 byes, and was difficult to test in isolation. This
  module is purely "wikitext in, structured rows out" — every transformation
  is a small, named, individually-testable step.

How tennis Wikipedia pages are built:

  1. ONE "Finals" template at the top of the Draw section — covers the
     last three rounds (QF / SF / F for any draw ≥ 8 players).
       Slam / Masters 1000:  8TeamBracket-Tennis5  /  8TeamBracket-Tennis3
       (Some pages use the -v2 variant; same key schema, slightly different
        cosmetic args.)

  2. N "Section" templates (one per Section N subsection in the page),
     each covering one slice of the draw from its first round down to the
     player who advances to QF.
       16-slot section (Slam, no byes):       16TeamBracket-Compact-Tennis5
       16-slot section (Masters 1000, byes):  16TeamBracket-Compact-Tennis3-Byes
       8-slot section (ATP/WTA 500):          8TeamBracket-Compact-Tennis3-Byes
       (etc.)

  Within each template:
    RDi-seed{NN}              entry seed ("1", "Q", "WC", "LL", or unseeded)
    RDi-team{NN}              flag template + wikilink, bold if winner
    RDi-score{NN}-{set}       per-set score, bold if won, <sup>N</sup> for TB

Round labels ("First round", etc.) are derived from structural counts,
not trusted verbatim — RD1 means R128 in a 128-draw and R64 in a 64-draw,
so the parser returns absolute round names.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from typing import Iterator

import httpx

log = logging.getLogger(__name__)

# Map "leaf round size" (= total_leaf_slots) to a tuple of round names from
# the first round to the Final. Anything not in the table is unsupported and
# parsing bails out cleanly.
_ROUND_NAMES_BY_DRAW: dict[int, tuple[str, ...]] = {
    128: ("R128", "R64", "R32", "R16", "QF", "SF", "F"),
    64:  ("R64", "R32", "R16", "QF", "SF", "F"),
    48:  ("R64", "R32", "R16", "QF", "SF", "F"),   # 32 byes from 48-draw 250s
    32:  ("R32", "R16", "QF", "SF", "F"),
    16:  ("R16", "QF", "SF", "F"),
    8:   ("QF", "SF", "F"),
}


# ---------------------------------------------------------------------------
# Output model
# ---------------------------------------------------------------------------


@dataclass
class WikiPlayer:
    """One team cell. For singles the team is one player; for doubles it's
    a pair, but we treat the wikilink target as opaque for now since the
    rest of the pipeline only resolves singles. Doubles support comes later."""

    wikilink: str | None              # canonical Wikipedia title, e.g. "Jannik Sinner"
    display_name: str | None          # display alias from [[X|Y]], else same as wikilink
    country_iso3: str | None          # from {{flagicon|XXX}}
    seed: str | None                  # "1", "Q", "WC", "LL", or None
    won: bool                         # team_wikitext was bolded

    def __repr__(self) -> str:
        return f"WikiPlayer({self.wikilink!r}, seed={self.seed!r}, won={self.won})"


@dataclass
class WikiMatch:
    """One parsed match cell from the bracket."""

    round_name: str                   # absolute: "R128" / "R64" / ... / "F"
    bracket_position: int             # 0-indexed position WITHIN that round
    team1: WikiPlayer | None
    team2: WikiPlayer | None
    score: str | None                 # canonical "6-4 7(7)-6(2) 6-3"
    is_bye: bool                      # both teams empty
    raw_section: int | None           # which section template (1..N), or None for Finals

    def __repr__(self) -> str:
        t1 = self.team1.wikilink if self.team1 else "—"
        t2 = self.team2.wikilink if self.team2 else "—"
        return f"WikiMatch({self.round_name}#{self.bracket_position} {t1} vs {t2} score={self.score!r})"


@dataclass
class ParsedBracket:
    page_title: str
    draw_size: int                    # 128 / 64 / 32 / ...
    section_count: int
    slots_per_section: int            # 16 / 8 / 4
    round_names: tuple[str, ...]      # round labels in order R128..F or R64..F etc.
    matches: list[WikiMatch] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# MediaWiki fetch
# ---------------------------------------------------------------------------


_API = "https://en.wikipedia.org/w/api.php"


def fetch_wikitext(page_title: str, client: httpx.Client | None = None) -> str:
    """Pull the wikitext for one tournament page. Tiny wrapper; broken out
    so tests can pass canned input via parse_wikitext().

    User-Agent follows Wikipedia's API etiquette
    (https://meta.wikimedia.org/wiki/User-Agent_policy): identifies the
    tool + a contact URL. Generic "Mozilla/X.0" UAs are aggressively
    rate-limited (429), which had been intermittently breaking apply
    runs.
    """
    own_client = client is None
    c = client or httpx.Client(
        timeout=15.0,
        headers={"User-Agent": "Mobtennis/1.0 (+https://mob.tennis; bot@mob.tennis)"},
    )
    try:
        r = c.get(_API, params={
            "action": "parse",
            "page": page_title,
            "format": "json",
            "prop": "wikitext",
            "formatversion": "2",
        })
        r.raise_for_status()
        data = r.json()
        wt = data.get("parse", {}).get("wikitext")
        if not isinstance(wt, str):
            raise ValueError(f"No wikitext for {page_title!r}: {data}")
        return wt
    finally:
        if own_client:
            c.close()


# ---------------------------------------------------------------------------
# Balanced-token scanning
# ---------------------------------------------------------------------------


def _find_balanced(s: str, open_tok: str, close_tok: str, start: int) -> int:
    """Given that s[start:start+len(open_tok)] == open_tok, return the index
    just AFTER the matching close_tok, accounting for nesting of the same
    pair. Raises ValueError if unbalanced.

    We deliberately don't handle nested *different* delimiters here — the
    inner scanner is naive about [[...]] vs {{...}}, which is fine because
    Wikipedia templates don't have unbalanced inner brackets in practice.
    """
    if not s.startswith(open_tok, start):
        raise ValueError(f"expected {open_tok!r} at pos {start}")
    depth = 0
    i = start
    n = len(s)
    while i < n:
        if s.startswith(open_tok, i):
            depth += 1
            i += len(open_tok)
        elif s.startswith(close_tok, i):
            depth -= 1
            i += len(close_tok)
            if depth == 0:
                return i
        else:
            i += 1
    raise ValueError(f"unbalanced {open_tok}...{close_tok}")


def _split_template_args(body: str) -> list[str]:
    """Split a template body (the content between '{{Name' and '}}') on
    top-level '|' separators. Respects nested {{...}} and [[...]] so values
    containing flagicons or piped wikilinks don't get sliced apart."""
    out: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(body)
    while i < n:
        c = body[i]
        if c == "|":
            out.append("".join(buf))
            buf = []
            i += 1
            continue
        if body.startswith("{{", i):
            j = _find_balanced(body, "{{", "}}", i)
            buf.append(body[i:j])
            i = j
            continue
        if body.startswith("[[", i):
            j = _find_balanced(body, "[[", "]]", i)
            buf.append(body[i:j])
            i = j
            continue
        buf.append(c)
        i += 1
    out.append("".join(buf))
    return out


# ---------------------------------------------------------------------------
# Template extraction
# ---------------------------------------------------------------------------


_TEMPLATE_NAME_RE = re.compile(r"\{\{(\d+TeamBracket[A-Za-z0-9\-]*)")


@dataclass
class _RawTemplate:
    name: str
    body: str                          # everything between the name and the closing }}
    kind: str                          # "finals" | "section" | "qualifier" | "unknown"
    slot_count: int                    # derived from template name prefix (8/16/...)


def _classify(name: str) -> str:
    """Categorise a bracket template by name."""
    low = name.lower()
    if "compact" in low:
        return "section"
    # Plain N-TeamBracket-Tennis{,3,5,-v2} → Finals subtree (QF/SF/F or SF/F for 4-player).
    if "tennis" in low:
        return "finals"
    return "unknown"


def _extract_templates(wikitext: str) -> list[_RawTemplate]:
    """Walk the page top to bottom, yielding every NTeamBracket-* template
    in document order. Order matters: section templates are numbered
    1..N by their position on the page."""
    out: list[_RawTemplate] = []
    for m in _TEMPLATE_NAME_RE.finditer(wikitext):
        name = m.group(1)
        # Match number prefix: 8 / 16 / 32 / 4.
        prefix_match = re.match(r"(\d+)", name)
        slot_count = int(prefix_match.group(1)) if prefix_match else 0
        # Find the surrounding {{...}}.
        opener_start = m.start()
        try:
            end = _find_balanced(wikitext, "{{", "}}", opener_start)
        except ValueError as e:
            log.warning("template %s: %s", name, e)
            continue
        body = wikitext[opener_start + 2 + len(name): end - 2]
        out.append(_RawTemplate(name=name, body=body, kind=_classify(name), slot_count=slot_count))
    return out


# ---------------------------------------------------------------------------
# Cell parsing
# ---------------------------------------------------------------------------


# Slot numbers are 1- or 2-digit. The 16-slot section templates use
# zero-padded "team01"; the 8-slot Finals + 4-slot qualifier templates
# use bare "team1". \d{1,2} covers both — they're never ambiguous because
# the prefix "team"/"seed"/"score" terminates after the digits.
_KEY_RE = re.compile(
    r"^\s*RD(\d+)-(seed|team|score)(\d{1,2})(?:-(\d+))?\s*$",
    re.IGNORECASE,
)
_BOLD_RE = re.compile(r"^\s*'''(.*?)'''\s*$", re.DOTALL)
_FLAG_RE = re.compile(r"\{\{flagicon\|\s*([A-Za-z]{2,3})?\s*\}\}", re.IGNORECASE)
_WIKILINK_RE = re.compile(r"\[\[([^\[\]\|]+?)(?:\|([^\[\]]+?))?\]\]")
_SUP_RE = re.compile(r"<sup>(.*?)</sup>", re.IGNORECASE | re.DOTALL)


def _parse_team_value(raw: str) -> tuple[WikiPlayer | None, bool]:
    """Parse one RDi-team{NN}=... cell. Returns (player, won_flag).

    won_flag is also returned via player.won; both surfaces match.
    Empty / whitespace-only cells return (None, False) — that's a bye.
    """
    s = raw.strip()
    if not s:
        return None, False
    won = False
    m = _BOLD_RE.match(s)
    if m:
        won = True
        s = m.group(1)
    # Flag icon (may be empty `{{flagicon|}}` for unknown country).
    country = None
    flag = _FLAG_RE.search(s)
    if flag and flag.group(1):
        country = flag.group(1).upper()
    s_no_flag = _FLAG_RE.sub("", s).strip()
    # Wikilink: [[Target|Display]] or [[Target]].
    wikilink = None
    display = None
    wl = _WIKILINK_RE.search(s_no_flag)
    if wl:
        wikilink = wl.group(1).strip()
        display = (wl.group(2) or wl.group(1)).strip()
    elif s_no_flag and not s_no_flag.startswith("[["):
        # Plain text fallback — uncommon, e.g. "Bye" written as text.
        display = s_no_flag
    if wikilink is None and display is None:
        return None, won
    return (
        WikiPlayer(
            wikilink=wikilink,
            display_name=display,
            country_iso3=country,
            seed=None,
            won=won,
        ),
        won,
    )


def _parse_score_value(raw: str) -> tuple[str, bool]:
    """Parse one RDi-score{NN}-{set}=... cell. Returns (clean_score, won_set).

    Tiebreak <sup>N</sup> is preserved inline as "7(7)" style — that's our
    canonical format. Empty cells return ("", False)."""
    s = raw.strip()
    if not s:
        return "", False
    won = False
    m = _BOLD_RE.match(s)
    if m:
        won = True
        s = m.group(1)
    # 6<sup>4</sup> → 6(4); 7<sup>7</sup> → 7(7)
    s = _SUP_RE.sub(lambda mm: f"({mm.group(1).strip()})", s)
    return s.strip(), won


def _index_template_cells(body: str) -> dict[tuple[int, str, int], str | None]:
    """Walk one template body and return a flat dict mapping
    (rd_index, kind, slot, set_or_none) → raw_value, EXCEPT score cells which
    include the set index. We model it as two dicts conceptually but flatten
    by using None for non-score cells.

    Concretely the key is (rd, kind, slot) and value is:
      - for seed/team:   the raw string
      - for score:       a dict {set_index: raw_string}
    """
    seed_team: dict[tuple[int, str, int], str] = {}
    scores: dict[tuple[int, int], dict[int, str]] = {}  # (rd, slot) → {set: raw}
    for arg in _split_template_args(body):
        if "=" not in arg:
            continue
        key, _, val = arg.partition("=")
        m = _KEY_RE.match(key)
        if not m:
            continue
        rd = int(m.group(1))
        kind = m.group(2).lower()
        slot = int(m.group(3))
        set_idx = int(m.group(4)) if m.group(4) else None
        if kind in ("seed", "team"):
            seed_team[(rd, kind, slot)] = val
        elif kind == "score":
            assert set_idx is not None, f"score cell without set index: {key}"
            scores.setdefault((rd, slot), {})[set_idx] = val
    # Re-emit scores under (rd, "score", slot) → joined-by-sets dict-as-str.
    # We don't merge to a final string here — _build_match does that so it
    # can decide ordering once both team scores are paired.
    out: dict[tuple[int, str, int], str | None] = {}
    out.update(seed_team)
    for (rd, slot), sets in scores.items():
        # Stable serialisation: comma-joined "set:raw" entries.
        # _build_match parses this back.
        out[(rd, "score", slot)] = ";".join(
            f"{i}:{sets[i]}" for i in sorted(sets.keys())
        )
    return out


def _parse_section_scores(raw: str | None) -> dict[int, tuple[str, bool]]:
    """Inverse of the encoding done in _index_template_cells."""
    if not raw:
        return {}
    out: dict[int, tuple[str, bool]] = {}
    for chunk in raw.split(";"):
        if not chunk or ":" not in chunk:
            continue
        idx_s, _, val = chunk.partition(":")
        try:
            idx = int(idx_s)
        except ValueError:
            continue
        out[idx] = _parse_score_value(val)
    return out


def _format_score(team1_sets: dict[int, tuple[str, bool]],
                  team2_sets: dict[int, tuple[str, bool]]) -> str | None:
    """Compose a canonical score string from per-set values.

    Example output: "6-4 7(7)-6(2) 6-3". Empty sets are dropped from the
    tail. Returns None if no sets at all (unplayed match)."""
    all_sets = sorted(set(team1_sets.keys()) | set(team2_sets.keys()))
    sets_out: list[str] = []
    for i in all_sets:
        s1 = team1_sets.get(i, ("", False))[0]
        s2 = team2_sets.get(i, ("", False))[0]
        if not s1 and not s2:
            continue
        sets_out.append(f"{s1}-{s2}")
    return " ".join(sets_out) if sets_out else None


# ---------------------------------------------------------------------------
# Building matches from a template
# ---------------------------------------------------------------------------


def _clean_seed(raw: str | None) -> str | None:
    """Normalise seed values from the wikitext. Empty / whitespace / HTML
    entities (`&nbsp;`, `&#160;`) all mean 'no seed'."""
    if not raw:
        return None
    s = raw.strip()
    # Strip common wiki non-breaking-space encodings.
    s = s.replace("&nbsp;", "").replace("&#160;", "").replace(" ", "")
    s = s.strip()
    return s or None


def _slot_pair_indices(slot_count_in_round: int) -> Iterator[tuple[int, int, int]]:
    """For a round with K slots, yield (pair_index, slot_a, slot_b) for
    each adjacent pair. Wikipedia uses 1-based slot numbering with zero-
    padded {NN} keys, so slots are 1,2 / 3,4 / 5,6 / ... pair_index is
    0-based."""
    for pair in range(slot_count_in_round // 2):
        yield pair, 2 * pair + 1, 2 * pair + 2


def _round_max_slots(template_slot_count: int) -> dict[int, int]:
    """For a section template with N total slots:
      RD1 has N slots (N/2 matches)
      RD2 has N/2 slots (N/4 matches)
      ... down to RD_log2(N) which has 2 slots (1 match)."""
    out: dict[int, int] = {}
    rd = 1
    n = template_slot_count
    while n >= 2:
        out[rd] = n
        n //= 2
        rd += 1
    return out


def _build_matches_for_template(
    tpl: _RawTemplate,
    section_index: int | None,
    round_name_lookup: list[str],
    global_position_offset: dict[int, int],
) -> Iterator[WikiMatch]:
    """Walk every (round, pair) in this template and yield a WikiMatch.

    round_name_lookup[i] is the absolute round name (e.g., "R128") for
    RDi (1-indexed RD numbering, so look up index i-1).

    global_position_offset[rd] is the position offset for this template's
    RD{rd} matches in the global per-round numbering (zero for the very
    first section's RD1)."""
    cells = _index_template_cells(tpl.body)
    max_slots = _round_max_slots(tpl.slot_count)
    for rd, slot_count in max_slots.items():
        if rd > len(round_name_lookup):
            # Template has more rounds than the round-name lookup covers.
            # For section templates this means the template's deeper rounds
            # are actually part of the Finals template's domain (e.g. Halle
            # 32-draw: 16-slot section physically has 4 rounds, but only
            # the first 3 are "real"; the 4th's data, if any, would
            # duplicate the Finals template's RD1). Skip cleanly.
            continue
        round_name = round_name_lookup[rd - 1]
        offset = global_position_offset.get(rd, 0)
        for pair_idx, slot_a, slot_b in _slot_pair_indices(slot_count):
            team1_raw = cells.get((rd, "team", slot_a))
            team2_raw = cells.get((rd, "team", slot_b))
            team1, _ = _parse_team_value(team1_raw or "")
            team2, _ = _parse_team_value(team2_raw or "")
            seed1_raw = cells.get((rd, "seed", slot_a))
            seed2_raw = cells.get((rd, "seed", slot_b))
            if team1:
                team1.seed = _clean_seed(seed1_raw)
            if team2:
                team2.seed = _clean_seed(seed2_raw)
            s1 = _parse_section_scores(cells.get((rd, "score", slot_a)))
            s2 = _parse_section_scores(cells.get((rd, "score", slot_b)))
            score = _format_score(s1, s2)
            yield WikiMatch(
                round_name=round_name,
                bracket_position=offset + pair_idx,
                team1=team1,
                team2=team2,
                score=score,
                is_bye=(team1 is None and team2 is None),
                raw_section=section_index,
            )


# ---------------------------------------------------------------------------
# Top-level parser
# ---------------------------------------------------------------------------


def parse_wikitext(page_title: str, wikitext: str) -> ParsedBracket:
    """Parse a tournament's wikitext into a structured ParsedBracket."""
    raw = _extract_templates(wikitext)

    sections = [t for t in raw if t.kind == "section"]
    # The actual main-draw Finals template is whichever 'finals'-shaped
    # template appears BEFORE the first section template (always
    # document order). Subsequent finals-shaped templates are qualifier
    # brackets (4TeamBracket-Tennis*) — we skip those for v1.
    first_section_idx = next((i for i, t in enumerate(raw) if t.kind == "section"), len(raw))
    finals = [
        raw[i] for i in range(first_section_idx) if raw[i].kind == "finals"
    ]

    warnings: list[str] = []

    if not sections:
        # Tiny events sometimes have just a Finals bracket and no Section
        # templates (8-player exhibitions, BJK/ATP Cup ties). Punt for now.
        return ParsedBracket(
            page_title=page_title,
            draw_size=0,
            section_count=0,
            slots_per_section=0,
            round_names=(),
            warnings=["no section templates found"],
        )

    slots_per_section = sections[0].slot_count
    if any(s.slot_count != slots_per_section for s in sections):
        warnings.append(
            f"section templates have inconsistent slot counts: "
            f"{[s.slot_count for s in sections]}"
        )

    section_count = len(sections)
    total_leaf_slots = slots_per_section * section_count

    round_names = _ROUND_NAMES_BY_DRAW.get(total_leaf_slots)
    if round_names is None:
        warnings.append(
            f"unsupported draw size {total_leaf_slots} "
            f"({section_count} sections × {slots_per_section} slots)"
        )
        return ParsedBracket(
            page_title=page_title,
            draw_size=total_leaf_slots,
            section_count=section_count,
            slots_per_section=slots_per_section,
            round_names=(),
            warnings=warnings,
        )

    matches: list[WikiMatch] = []

    # How many rounds the section templates actually cover. This depends on
    # the size of the Finals template: with an 8-slot Finals and 8 sections,
    # each section produces 1 entrant (its RD4 winner in a 16-slot section);
    # with a 4-slot Finals and 2 sections, each section produces 2 entrants
    # (its RD3 winners — RD4 doesn't exist in the data). Naively assuming
    # sections cover all of log2(slots_per_section) rounds previously caused
    # the Halle 2025 case (32-draw, 2 sections × 16 slots, 4-slot Finals)
    # to mis-label SF and F.
    if finals:
        finals_slot_count = finals[0].slot_count
        entrants_per_section = max(1, finals_slot_count // section_count)
        section_rounds_used = int(math.log2(slots_per_section // entrants_per_section))
    else:
        # No Finals template — sections cover everything they have.
        finals_slot_count = 0
        section_rounds_used = int(math.log2(slots_per_section))
        warnings.append("no Finals template; sections cover all rounds")

    section_round_names = list(round_names[:section_rounds_used])
    finals_round_names = list(round_names[section_rounds_used:])

    rounds_in_section = _round_max_slots(slots_per_section)  # rd → slot count

    for s_idx, tpl in enumerate(sections, start=1):
        offsets: dict[int, int] = {}
        for rd in range(1, section_rounds_used + 1):
            slot_count = rounds_in_section.get(rd, 0)
            pairs_per_section = slot_count // 2
            offsets[rd] = (s_idx - 1) * pairs_per_section
        for m in _build_matches_for_template(tpl, s_idx, section_round_names, offsets):
            matches.append(m)

    # --- Finals: positions are global within the Finals subtree. No section
    # offset to apply. Round name lookup is whatever's left after the
    # sections claim their prefix.
    for tpl in finals:
        offsets = {rd: 0 for rd in _round_max_slots(tpl.slot_count)}
        for m in _build_matches_for_template(tpl, None, finals_round_names, offsets):
            matches.append(m)

    return ParsedBracket(
        page_title=page_title,
        draw_size=total_leaf_slots,
        section_count=section_count,
        slots_per_section=slots_per_section,
        round_names=round_names,
        matches=matches,
        warnings=warnings,
    )


def parse_page(page_title: str, client: httpx.Client | None = None) -> ParsedBracket:
    """Convenience wrapper: fetch + parse in one call."""
    wikitext = fetch_wikitext(page_title, client=client)
    return parse_wikitext(page_title, wikitext)


__all__ = [
    "WikiPlayer",
    "WikiMatch",
    "ParsedBracket",
    "parse_wikitext",
    "parse_page",
    "fetch_wikitext",
]
