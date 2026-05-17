"""Wikipedia tournament-draw scraper.

api-tennis ships fixtures and scores but not draw structure — no seeds,
no bracket position, no byes. For top-tier events (Slams, ATP/WTA 1000)
Wikipedia publishes the bracket as a wikitext template (`{{16TeamBracket-Tennis5}}`
and siblings) before the tournament starts. We parse that and:

  - assign each existing Match a `bracket_position` so the UI can render
    a structurally correct bracket
  - attach `player1_seed` / `player2_seed`
  - record byes as Match rows with one null player + status="walkover"
    so the bracket UI has an explicit slot to render "Bye"

Sackmann always wins when it runs later — match_num + seed columns from
Sackmann's CSVs are authoritative for completed events. Wikipedia is the
live-event fill-in.

Curated map of tournament slug → Wikipedia page title prefix. Only the
tournaments we expect to have a Wikipedia draw are included; unknown
slugs are silently skipped and the tournament page renders without a
bracket section. Adding new tournaments is a one-line addition here.
"""

from __future__ import annotations

import asyncio
import gc
import logging
import re
import unicodedata
from datetime import date, timedelta
from dataclasses import dataclass
from typing import Iterable

import httpx
from sqlmodel import Session, select

from app.db.session import engine

from app.models.match import Match, MatchStatus
from app.models.player import Player, Tour
from app.models.tournament import Tournament, TournamentCategory
from app.services.player_dedup import _fuzzy_initial_match, find_player_by_name, name_key

log = logging.getLogger(__name__)

USER_AGENT = "MobtennisBot/1.0 (https://mob.tennis)"
WIKI_API = "https://en.wikipedia.org/w/api.php"


# Slug → Wikipedia "tournament name" the title uses. The full title is
# usually "{year} {NAME} – {Men's|Women's|Mixed} {singles|doubles}".
# Doubles draws have their own page; we fetch them separately on demand.
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
}


# Tournament categories we attempt to scrape. Lower tiers don't reliably
# have Wikipedia draw pages so we skip them.
SCRAPABLE_CATEGORIES = {
    TournamentCategory.GRAND_SLAM,
    TournamentCategory.ATP_1000,
    TournamentCategory.WTA_1000,
    TournamentCategory.ATP_FINALS,
    TournamentCategory.WTA_FINALS,
}


@dataclass
class ParsedBracketMatch:
    """One match parsed from a Wikipedia bracket template."""
    block_kind: str                # "section" or "summary"
    section_idx: int               # 0-indexed; ignored for summary blocks
    rd_index: int                  # 1-indexed within the block
    position: int                  # 1-indexed slot within (block, rd)
    p1_name: str | None
    p1_seed: int | None
    p2_name: str | None
    p2_seed: int | None
    is_bye: bool                   # one slot literally reads "Bye"


@dataclass
class ParsedBlock:
    """A whole bracket block — either an early-rounds section (one octant
    of a 128-draw, say) or the late-round summary (QF/SF/F)."""
    kind: str                      # "section" or "summary"
    rd_labels: dict[int, str]      # raw labels from the template (RD1, RD2, …)
    matches: list[ParsedBracketMatch]
    section_slots: int             # 2^rd_count — total seedable slots in this block


# ---- Wikipedia fetch -------------------------------------------------------


async def _fetch_wikitext(client: httpx.AsyncClient, page_title: str) -> str | None:
    """Fetch raw wikitext for a page. Returns None if the page doesn't exist."""
    params = {
        "action": "query",
        "prop": "revisions",
        "rvprop": "content",
        "rvslots": "main",
        "format": "json",
        "titles": page_title,
        "redirects": 1,
    }
    try:
        r = await client.get(WIKI_API, params=params, timeout=15.0)
        r.raise_for_status()
    except httpx.HTTPError:
        return None
    data = r.json()
    pages = (data.get("query") or {}).get("pages") or {}
    for _, page in pages.items():
        if page.get("missing") is not None:
            return None
        revs = page.get("revisions") or []
        if not revs:
            return None
        slots = revs[0].get("slots") or {}
        main = slots.get("main") or {}
        text = main.get("*") or main.get("content")
        if isinstance(text, str):
            return text
    return None


def _wiki_title_for(t: Tournament, doubles: bool, mixed: bool = False) -> str | None:
    """Compose the Wikipedia page title for a tournament's draw, or None
    if we don't have a mapping for this brand."""
    name = SLUG_TO_WIKI_NAME.get(t.slug)
    if not name:
        return None
    if mixed:
        bracket = "Mixed doubles"
    else:
        gender = "Men's" if t.tour == Tour.ATP else "Women's"
        bracket = f"{gender} {'doubles' if doubles else 'singles'}"
    # The en-dash separator is what Wikipedia uses for tennis-draw subpages.
    return f"{t.year} {name} – {bracket}"


# ---- Parser ---------------------------------------------------------------


# Match the top-level tennis bracket templates. We want the body between
# `{{NTeamBracket-Tennis...}}` and the matching closing `}}`. Brackets are
# nested with templates inside (RD1-team etc. can have wiki-links), so we
# walk the string balancing braces.
_BRACKET_TEMPLATE_NAMES = re.compile(
    r"\{\{\s*(\d+(?:Round|Team)Bracket(?:-(?:Tennis\d|Compact-Tennis\d))?)\b",
    re.IGNORECASE,
)


def _extract_bracket_blocks(wikitext: str) -> list[str]:
    """Pull every tennis-bracket template body out of the page."""
    out: list[str] = []
    for m in _BRACKET_TEMPLATE_NAMES.finditer(wikitext):
        start = m.start()
        # Walk forward, balance `{{ }}` pairs.
        i = start
        depth = 0
        while i < len(wikitext) - 1:
            two = wikitext[i:i + 2]
            if two == "{{":
                depth += 1
                i += 2
            elif two == "}}":
                depth -= 1
                i += 2
                if depth == 0:
                    out.append(wikitext[start:i])
                    break
            else:
                i += 1
    return out


# Each bracket key looks like RD<round>-(seed|team|score)<N>[-set]. Position
# is 1 to 3 digits — big-draw templates use zero-padded `RD1-team01`, the
# smaller 8-team summary uses unpadded `RD1-team1`.
_RD_KEY = re.compile(
    r"\bRD(?P<rd>\d+)-(?P<kind>seed|team|score)(?P<pos>\d{1,3})(?:-(?P<set>\d))?\s*=",
    re.IGNORECASE,
)


_SUMMARY_RD1_HINTS = ("quarterfinal", "semifinal", "final")


def _parse_bracket_block(block: str, section_idx: int) -> ParsedBlock | None:
    """Pull (round, position) → seed/team/score from one bracket template.

    Templates lay participants out in pairs: positions 01 + 02 = first match
    in round 1; 03 + 04 = second match; … In round 2 the pair indices restart.
    We also read the template's `RD1=...`, `RD2=...` labels to classify the
    block as the late-rounds "summary" (RD1=Quarterfinals etc.) vs an
    early-rounds "section" (RD1=First round etc.).
    """
    cells: dict[tuple[int, int], dict[str, str]] = {}
    rd_labels: dict[int, str] = {}
    for kv in _split_template_args(block):
        # RD label like `|RD1=First round`
        m_label = re.match(r"\bRD(\d+)\s*=\s*(.+)$", kv, re.IGNORECASE | re.DOTALL)
        if m_label and "team" not in m_label.group(2).lower()[:10]:
            label = m_label.group(2).strip()
            # `RD1-team01` matches this regex too because of `RD1=` prefix; the
            # value would start with `team01=...`. The `team` filter above
            # mostly catches it, but be paranoid: skip if label has `-` keys.
            if "=" not in label and "{" not in label:
                rd_labels[int(m_label.group(1))] = label
                continue
        m = _RD_KEY.match(kv)
        if not m:
            continue
        rd = int(m.group("rd"))
        pos = int(m.group("pos"))
        kind = m.group("kind").lower()
        value = kv[m.end():].strip()
        cell = cells.setdefault((rd, pos), {})
        if kind == "score" and m.group("set"):
            cell[f"score{m.group('set')}"] = value
        else:
            cell[kind] = value

    if not cells:
        return None

    # Classify by RD1 label.
    rd1_label = (rd_labels.get(1) or "").lower()
    kind = "summary" if any(h in rd1_label for h in _SUMMARY_RD1_HINTS) else "section"

    # Walk slot positions in pairs. The template uses 1-indexed slot numbers;
    # pair (1, 2) is the topmost match, pair (3, 4) is next down, etc. The
    # match's position within the round = (top_slot - 1) // 2  (0-indexed),
    # which is stable across byes — a missing pair just leaves a hole.
    out: list[ParsedBracketMatch] = []
    rounds = sorted({rd for (rd, _) in cells.keys()})
    for rd in rounds:
        positions = sorted(p for (r, p) in cells.keys() if r == rd)
        seen_pairs: set[int] = set()
        for slot in positions:
            top = slot if slot % 2 == 1 else slot - 1
            if top in seen_pairs:
                continue
            seen_pairs.add(top)
            top_cell = cells.get((rd, top)) or {}
            bot_cell = cells.get((rd, top + 1)) or {}
            p1_name = _clean_wiki_name(top_cell.get("team"))
            p2_name = _clean_wiki_name(bot_cell.get("team"))
            is_bye = (
                (p1_name is not None and p1_name.lower() == "bye")
                or (p2_name is not None and p2_name.lower() == "bye")
            )
            out.append(ParsedBracketMatch(
                block_kind=kind,
                section_idx=section_idx,
                rd_index=rd,
                position=(top - 1) // 2,  # 0-indexed slot pair within the round
                p1_name=None if (p1_name and p1_name.lower() == "bye") else p1_name,
                p1_seed=_parse_int(top_cell.get("seed")),
                p2_name=None if (p2_name and p2_name.lower() == "bye") else p2_name,
                p2_seed=_parse_int(bot_cell.get("seed")),
                is_bye=bool(is_bye),
            ))

    if not out:
        return None

    # Section size = 2^(round count) — a clean derivation that side-steps
    # bye-driven gaps in the RD1 slot range.
    rd_count = max(m.rd_index for m in out)
    section_slots = max(2 ** rd_count, 2)
    return ParsedBlock(
        kind=kind,
        rd_labels=rd_labels,
        matches=out,
        section_slots=section_slots,
    )


def _split_template_args(block: str) -> Iterable[str]:
    """Yield each ``|key=value`` argument of a template. The body still has
    embedded `[[...]]` and nested `{{...}}` we need to skip over without
    treating their internal pipes as argument separators."""
    # Trim the outer `{{ ... }}` and the template name up to first `|`.
    inner = block.strip()
    if inner.startswith("{{"):
        inner = inner[2:]
    if inner.endswith("}}"):
        inner = inner[:-2]
    # Drop template name.
    first_pipe = inner.find("|")
    if first_pipe < 0:
        return
    inner = inner[first_pipe + 1:]

    buf: list[str] = []
    depth_braces = 0
    depth_brackets = 0
    for ch in inner:
        if ch == "{":
            depth_braces += 1
        elif ch == "}":
            depth_braces = max(0, depth_braces - 1)
        elif ch == "[":
            depth_brackets += 1
        elif ch == "]":
            depth_brackets = max(0, depth_brackets - 1)
        if ch == "|" and depth_braces == 0 and depth_brackets == 0:
            yield "".join(buf).strip()
            buf = []
        else:
            buf.append(ch)
    if buf:
        yield "".join(buf).strip()


def _clean_wiki_name(value: str | None) -> str | None:
    """Strip wiki link syntax and flag templates around a player name.

    Examples:
      "[[Jannik Sinner]]"                       → "Jannik Sinner"
      "[[Jannik Sinner|Jannik Sinner (ITA)]]"   → "Jannik Sinner (ITA)"
      "{{flagicon|ITA}} [[Jannik Sinner]]"      → "Jannik Sinner"
      "''Jannik Sinner''"                       → "Jannik Sinner"
    """
    if value is None:
        return None
    s = value.strip()
    # Drop {{flagicon|XYZ}} / {{flag|XYZ}} / similar one-arg templates.
    s = re.sub(r"\{\{[^{}]*?\}\}", "", s)
    # Wiki links: keep display text (after pipe) or page name.
    def _link(m: re.Match) -> str:
        body = m.group(1)
        if "|" in body:
            return body.split("|", 1)[1]
        return body
    s = re.sub(r"\[\[([^\[\]]+)\]\]", _link, s)
    # Italic / bold markup.
    s = re.sub(r"'{2,}", "", s)
    # Collapse whitespace.
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    s = value.strip()
    if not s or not s.isdigit():
        return None
    n = int(s)
    return n if 0 < n <= 64 else None  # sane seed range


# ---- Apply to DB ----------------------------------------------------------


# Canonical round labels indexed from the final (idx 0) back to the deepest
# possible early round. label_for(total_T, global_round_i) = _LABELS[T - i].
_LABELS = ["F", "SF", "QF", "R16", "R32", "R64", "R128", "R256"]


@dataclass
class DrawShape:
    """Resolved structure of a single Wikipedia tournament-draw page."""
    section_blocks: list[ParsedBlock]
    summary_block: ParsedBlock | None
    total_rounds: int
    # Round labels by 1-indexed global round number (1 = deepest early round).
    label_by_round: dict[int, str]


def _is_qualifying(block: ParsedBlock) -> bool:
    """True if this block is a qualifying mini-bracket — we ingest only the
    main draw, never quallies."""
    return any(
        "qualif" in (lbl or "").lower() for lbl in block.rd_labels.values()
    )


def _resolve_draw_shape(blocks: list[ParsedBlock]) -> DrawShape | None:
    """Categorise the blocks and figure out the overall round mapping."""
    if not blocks:
        return None
    blocks = [b for b in blocks if not _is_qualifying(b)]
    section_blocks = [b for b in blocks if b.kind == "section"]
    # If sections have heterogeneous sizes (rare but possible if there's
    # leftover noise), keep only the dominant size — the main-draw shape.
    if section_blocks:
        from collections import Counter
        sizes = Counter(b.section_slots for b in section_blocks)
        dominant = sizes.most_common(1)[0][0]
        section_blocks = [b for b in section_blocks if b.section_slots == dominant]
    summary_candidates = [b for b in blocks if b.kind == "summary"]
    # Some pages have multiple summary-style blocks (e.g., 8-team bracket
    # repeated for "Singles" + "Doubles" on the same page); take the one
    # whose RD count gets us to a Final.
    summary_block = None
    for sb in summary_candidates:
        rd_count = len(sb.rd_labels) or max((m.rd_index for m in sb.matches), default=0)
        if any("final" in (lbl or "").lower() for lbl in sb.rd_labels.values()):
            summary_block = sb
            break
    if summary_block is None and summary_candidates:
        summary_block = summary_candidates[0]

    # Use the template's declared RD labels for round count, not the
    # currently-played match rows — early in the tournament the final
    # has a label but no match yet.
    section_rounds = max(
        (max(b.rd_labels.keys(), default=0) for b in section_blocks),
        default=0,
    )
    summary_rounds = (
        max(summary_block.rd_labels.keys(), default=0) if summary_block else 0
    )
    total = section_rounds + summary_rounds
    if total == 0:
        return None
    if total > len(_LABELS):
        log.warning("wiki draw: total_rounds=%d exceeds known labels", total)
        return None

    label_by_round = {i + 1: _LABELS[total - i - 1] for i in range(total)}
    return DrawShape(
        section_blocks=section_blocks,
        summary_block=summary_block,
        total_rounds=total,
        label_by_round=label_by_round,
    )


def _match_for(
    session: Session,
    tournament_id: int,
    round_label: str,
    is_doubles: bool,
    p1_id: int | None,
    p2_id: int | None,
) -> Match | None:
    """Find the existing Match row in this tournament + round that has
    the given pair of players (order-insensitive)."""
    if p1_id is None and p2_id is None:
        return None
    stmt = select(Match).where(
        Match.tournament_id == tournament_id,
        Match.is_doubles == is_doubles,
    )
    candidates = session.exec(stmt).all()
    target_pair = {x for x in (p1_id, p2_id) if x is not None}
    for m in candidates:
        if not m.round:
            continue
        # Match by canonical round label (substring is OK — api-tennis
        # ships strings like "ATP Rome - 1/16-finals").
        if not _round_matches(m.round, round_label):
            continue
        pair = {x for x in (m.player1_id, m.player2_id) if x is not None}
        if pair and pair.issubset(target_pair):
            return m
    return None


def _round_matches(stored: str, want: str) -> bool:
    """True if a stored round label resolves to the desired canonical one."""
    s = stored.lower()
    if want == "F":
        return s.endswith("final") or s.endswith(" final") or s == "f"
    fragments = {
        "SF": ("semi-final", "semifinals", "semifinal"),
        "QF": ("quarter-final", "quarterfinals", "quarterfinal"),
        "R16": ("1/8-final", "round of 16", "r16"),
        "R32": ("1/16-final", "round of 32", "r32"),
        "R64": ("1/32-final", "round of 64", "r64"),
        "R128": ("1/64-final", "round of 128", "r128"),
    }
    needles = fragments.get(want, (want.lower(),))
    return any(n in s for n in needles)


async def scrape_tournament(
    client: httpx.AsyncClient,
    t: Tournament,
) -> int:
    """Scrape one tournament's singles draw (and doubles if available).
    Returns count of Match rows updated. 0 means we couldn't find / parse
    a draw — the tournament-page UI will then hide the bracket section.

    DB work is dispatched to a worker thread because _apply_draw_shape
    does many sync SQLAlchemy queries and was previously blocking the
    asyncio event loop for tens of seconds at a time. While that ran
    the WS consumer's keepalive timed out and every HTTP handler
    queued. Wikipedia fetch (httpx async) stays in the loop; the
    threaded worker opens its own short-lived session and commits when
    done.
    """
    if t.category not in SCRAPABLE_CATEGORIES:
        return 0

    total = 0
    for doubles in (False, True):
        title = _wiki_title_for(t, doubles=doubles)
        if title is None:
            continue
        wikitext = await _fetch_wikitext(client, title)
        if wikitext is None:
            continue
        blocks_raw = _extract_bracket_blocks(wikitext)
        parsed_blocks = [
            pb for i, b in enumerate(blocks_raw)
            if (pb := _parse_bracket_block(b, section_idx=i)) is not None
        ]
        # Re-number section_idx among only the actual section blocks.
        section_running = 0
        for pb in parsed_blocks:
            if pb.kind == "section":
                for m in pb.matches:
                    m.section_idx = section_running
                section_running += 1
        shape = _resolve_draw_shape(parsed_blocks)
        if shape is None:
            continue

        # Heavy DB work in a thread — see docstring rationale.
        updated = await asyncio.to_thread(
            _apply_and_commit, t.id, shape, doubles,
        )
        total += updated
        log.info(
            "wikipedia draw: %s%s → updated %d match(es)",
            title, " (doubles)" if doubles else "", updated,
        )

    return total


def _apply_and_commit(
    tournament_id: int | None,
    shape: DrawShape,
    is_doubles: bool,
) -> int:
    """Threaded worker. Opens a fresh session, applies the parsed draw,
    commits, returns the row count touched. Safe to call off the asyncio
    thread because the session is created and disposed within this scope."""
    if tournament_id is None:
        return 0
    with Session(engine) as session:
        t = session.get(Tournament, tournament_id)
        if t is None:
            return 0
        updated = _apply_draw_shape(session, t, shape, is_doubles)
        if updated:
            session.commit()
        return updated


def _apply_draw_shape(
    session: Session,
    tournament: Tournament,
    shape: DrawShape,
    is_doubles: bool,
) -> int:
    """Walk the parsed matches in a resolved draw, resolve player names,
    write bracket_position + seeds onto matching Match rows."""
    if tournament.id is None:
        return 0
    tour = tournament.tour
    section_rounds = max(
        (max(b.rd_labels.keys(), default=0) for b in shape.section_blocks),
        default=0,
    )
    # Preload the tour's player table once for fuzzy fallback (saves N×M
    # queries when resolving 100+ names per draw).
    tour_players = list(session.exec(
        select(Player).where(Player.tour == tour)
    ).all())
    # Player ids already referenced by Match rows for this tournament —
    # used to disambiguate duplicate Player rows. When api-tennis registered
    # a match under "S. Ofner" id=135640 and Sackmann seeded "Sebastian Ofner"
    # id=1136 separately, this set tells the resolver to pick the id our
    # actual matches use.
    preferred_ids = set()
    for m in session.exec(
        select(Match.player1_id, Match.player2_id).where(
            Match.tournament_id == tournament.id,
            Match.is_doubles == is_doubles,
        )
    ).all():
        for pid in m:
            if pid is not None:
                preferred_ids.add(pid)
    updated = 0

    for block in shape.section_blocks + (
        [shape.summary_block] if shape.summary_block else []
    ):
        for pm in block.matches:
            if block.kind == "section":
                global_round = pm.rd_index
            else:
                global_round = section_rounds + pm.rd_index
            round_label = shape.label_by_round.get(global_round)
            if not round_label:
                continue
            if pm.is_bye:
                # No Match row to update — the slot is structurally empty.
                # The UI infers the bye by following the seeded player
                # into the next round.
                continue

            # bracket_position: section blocks distribute slots across
            # sections; summary blocks are global already. pm.position is
            # already 0-indexed inside its section/block.
            if block.kind == "section":
                matches_per_section_in_round = max(
                    block.section_slots // (2 ** pm.rd_index), 1
                )
                bracket_position = (
                    pm.section_idx * matches_per_section_in_round
                    + pm.position
                )
            else:
                bracket_position = pm.position

            p1 = _resolve_player(session, pm.p1_name, tour, tour_players, preferred_ids) if pm.p1_name else None
            p2 = _resolve_player(session, pm.p2_name, tour, tour_players, preferred_ids) if pm.p2_name else None
            if p1 is None and p2 is None:
                continue
            match = _match_for(
                session, tournament.id, round_label, is_doubles,
                p1.id if p1 else None,
                p2.id if p2 else None,
            )
            if match is None:
                continue
            match.bracket_position = bracket_position
            # Map seeds onto the right slot — the existing match row's
            # player1/player2 ordering may not match Wikipedia's.
            if p1 is not None and match.player1_id == p1.id:
                match.player1_seed = pm.p1_seed
                match.player2_seed = pm.p2_seed
            elif p2 is not None and match.player1_id == p2.id:
                match.player1_seed = pm.p2_seed
                match.player2_seed = pm.p1_seed
            else:
                match.player1_seed = pm.p1_seed
                match.player2_seed = pm.p2_seed
            session.add(match)
            updated += 1
    return updated


def _normalize_lastname(name: str | None) -> str | None:
    """Take the last whitespace token and strip diacritics + casing.

    Wikipedia uses "Marozsán" / "Cerúndolo" / "Báez" with accent marks;
    api-tennis ships ASCII. Comparing the last token gets us most matches
    cheaply ("B van de Zandschulp" → "Zandschulp" matches "Botic van de
    Zandschulp" → "Zandschulp"). Hyphenated last names stay intact.
    """
    if not name:
        return None
    cleaned = name.strip()
    if not cleaned:
        return None
    tokens = re.split(r"\s+", cleaned)
    last = next((t for t in reversed(tokens) if t), None)
    if not last:
        return None
    decomposed = unicodedata.normalize("NFD", last)
    stripped = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return stripped.lower() or None


def _first_initial(name: str | None) -> str | None:
    """First letter of the first whitespace token, lowercased, ASCII-only.
    Handles compact initials like 'TM Etcheverry' → 't' and diacritic
    firsts like 'Ó'Connor' → 'o'.

    Diacritic-stripping has to happen BEFORE the non-letter strip,
    otherwise 'Ó' fails the [A-Za-z] filter and we'd skip ahead to the
    next letter (wrong: returned 'c' for 'Ó'Connor')."""
    if not name:
        return None
    tokens = [t for t in re.split(r"\s+", name.strip()) if t]
    if not tokens:
        return None
    decomposed = unicodedata.normalize("NFD", tokens[0])
    ascii_first = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    cleaned = re.sub(r"[^A-Za-z]", "", ascii_first)
    return cleaned[:1].lower() or None


def _resolve_player(
    session: Session,
    raw_name: str,
    tour: Tour,
    tour_players: list[Player] | None = None,
    preferred_ids: set[int] | None = None,
) -> Player | None:
    """Resolve a Wikipedia display name to one of our Player rows.

    Lookup is layered, cheapest first:

      1. `name_key` (sorted-token) exact — catches "Jannik Sinner" vs
         "Sinner, Jannik" with one indexed query.
      2. Diacritic-normalised last name — the most stable signal across
         sources. "Marozsán" vs "Marozsan", "B van de Zandschulp" vs
         "Botic van de Zandschulp", "F Cerúndolo" vs "Francisco Cerúndolo"
         all collapse to the same key. If two players share a last name
         on the same tour (e.g. two Cerúndolos), we disambiguate by the
         first letter of the first token.
      3. Initial-form fuzzy fallback — the same matcher dedupe uses, kept
         around for the rare case neither layer above caught it.
    """
    if not raw_name:
        return None
    cleaned = re.sub(r"\s*\([^)]*\)\s*$", "", raw_name).strip()
    if not cleaned:
        return None

    def _prefer(cands: list[Player]) -> Player | None:
        """Pick from a list of candidate Player rows, preferring those
        referenced in the tournament's existing matches. Resolves the
        duplicate-row case where api-tennis recorded a match under one
        Player (e.g. "S. Ofner") and Wikipedia ships another spelling
        ("Sebastian Ofner") that happens to live in a different row.

        Always returns a candidate when one exists — even when the signals
        can't disambiguate definitively, we tie-break on lowest id. That
        beats returning None (which would drop the match entirely), since
        the lowest-id row is typically the canonical Sackmann-seeded one.
        """
        if not cands:
            return None
        if len(cands) == 1:
            return cands[0]
        if preferred_ids:
            in_tour = [p for p in cands if p.id in preferred_ids]
            if len(in_tour) == 1:
                return in_tour[0]
            if len(in_tour) > 1:
                cands = in_tour
        target_init = _first_initial(raw_name)
        if target_init:
            init_matches = [p for p in cands if _first_initial(p.full_name) == target_init]
            if len(init_matches) == 1:
                return init_matches[0]
            if init_matches:
                cands = init_matches
        return min(cands, key=lambda p: p.id or 0)

    # Layer 1.
    direct = find_player_by_name(session, cleaned, tour)
    if direct is not None:
        if not preferred_ids or direct.id in preferred_ids:
            return direct
        # Layer-1 hit is on the "wrong" player row (not in this tournament).
        # Try harder — maybe there's a duplicate row that IS in the
        # tournament. Fall through to layer 2 / 3.

    if tour_players is None:
        tour_players = list(session.exec(
            select(Player).where(Player.tour == tour)
        ).all())

    # Layer 2.
    target_last = _normalize_lastname(cleaned)
    if target_last:
        candidates = [
            p for p in tour_players
            if p.full_name and _normalize_lastname(p.full_name) == target_last
        ]
        picked = _prefer(candidates)
        if picked is not None:
            return picked

    # Layer 3.
    fuzzy = [
        p for p in tour_players
        if p.full_name and _fuzzy_initial_match(cleaned, p.full_name)
    ]
    picked = _prefer(fuzzy)
    if picked is not None:
        return picked

    # Final fallback: original layer-1 hit if we had one.
    return direct


# ---- Job entry ------------------------------------------------------------


async def scrape_pending_draws(max_count: int = 30) -> int:
    """Walk in-progress / upcoming top-tier tournaments and pull their
    draws. Idempotent — re-running just re-applies any new bracket info.
    Returns total Match rows updated across all scraped tournaments.

    Memory-conscious: each scrape parses ~hundreds of KB of wikitext and
    holds the parsed blocks + a DB session in memory. On the 2 GB box,
    running 30 of these back-to-back tipped the kernel into memory-
    pressure mode (systemd-resolved flushed DNS caches and broke
    outbound networking until the next reboot). We now (a) only
    consider tournaments that are actually live or just-finished, which
    knocks the candidate set from "every Slam + Masters of the year" to
    "the handful currently playing", and (b) yield + force a gc cycle
    between scrapes so peak resident memory drops back to baseline
    before the next round.
    """
    today = date.today()
    # Recently-finished window: 7 days catches late draw corrections
    # without scraping every past tournament of the season.
    finished_cutoff = today - timedelta(days=7)
    upcoming_cutoff = today + timedelta(days=21)

    with Session(engine) as session:
        candidate_rows = session.exec(
            select(Tournament)
            .where(Tournament.category.in_(list(SCRAPABLE_CATEGORIES)))
            .where(
                (Tournament.start_date.is_(None))
                | (
                    (Tournament.start_date <= upcoming_cutoff)
                    & (
                        (Tournament.end_date.is_(None))
                        | (Tournament.end_date >= finished_cutoff)
                    )
                )
            )
            .order_by(Tournament.year.desc())
            .limit(max_count)
        ).all()
        candidates = [
            (t.id, t.slug, t.year, t.category, t.tour)
            for t in candidate_rows
        ]
    if not candidates:
        return 0

    total = 0
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}) as client:
        for tid, slug, year, category, tour in candidates:
            if slug not in SLUG_TO_WIKI_NAME:
                continue
            try:
                stub = Tournament(
                    id=tid, slug=slug, year=year, name=slug,
                    tour=tour, category=category,
                )
                total += await scrape_tournament(client, stub)
            except Exception:
                log.exception("draw scrape failed for %s %s", slug, year)
            # Yield + drop parsed wikitext / bracket structures before the
            # next round. Without this the scrape was the largest single
            # source of memory pressure on the box.
            gc.collect()
            await asyncio.sleep(0.5)
    return total
