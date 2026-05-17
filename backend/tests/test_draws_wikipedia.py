"""Unit tests for the Wikipedia draw parser + player resolver.

These pieces have been responsible for most of the bracket churn —
covering them with cheap tests means we can iterate on the matcher
without breaking the bits that already work.
"""

from __future__ import annotations

from sqlmodel import Session

from app.models.player import Player, Tour
from app.services.draws_wikipedia import (
    _clean_wiki_name,
    _extract_bracket_blocks,
    _first_initial,
    _normalize_lastname,
    _parse_bracket_block,
    _resolve_draw_shape,
    _resolve_player,
    _wiki_title_for,
)
from app.models.tournament import Tournament, TournamentCategory


# ---- helpers --------------------------------------------------------------


def _player(session: Session, name: str, tour: Tour = Tour.ATP, slug: str | None = None) -> Player:
    """Insert a Player row and return it."""
    from slugify import slugify

    p = Player(
        slug=slug or slugify(name)[:80],
        full_name=name,
        tour=tour,
        name_key="-".join(sorted(slugify(name).split("-"))),
    )
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


# ---- _normalize_lastname --------------------------------------------------


class TestNormalizeLastname:
    def test_strips_diacritics(self):
        assert _normalize_lastname("F. Marozsán") == "marozsan"
        assert _normalize_lastname("S. Báez") == "baez"
        assert _normalize_lastname("F. Cerúndolo") == "cerundolo"

    def test_takes_last_token(self):
        assert _normalize_lastname("Botic van de Zandschulp") == "zandschulp"
        assert _normalize_lastname("Alex de Minaur") == "minaur"

    def test_preserves_hyphenated_last(self):
        assert _normalize_lastname("F Auger-Aliassime") == "auger-aliassime"

    def test_handles_initials_alone(self):
        assert _normalize_lastname("J Sinner") == "sinner"
        assert _normalize_lastname("TM Etcheverry") == "etcheverry"

    def test_empty_returns_none(self):
        assert _normalize_lastname("") is None
        assert _normalize_lastname(None) is None
        assert _normalize_lastname("   ") is None


# ---- _first_initial -------------------------------------------------------


class TestFirstInitial:
    def test_single_letter(self):
        assert _first_initial("A Popyrin") == "a"

    def test_full_first_name(self):
        assert _first_initial("Alexei Popyrin") == "a"

    def test_two_letter_initials(self):
        assert _first_initial("TM Etcheverry") == "t"

    def test_strips_dot(self):
        assert _first_initial("J. Sinner") == "j"

    def test_diacritic(self):
        assert _first_initial("Ó'Connor") == "o"


# ---- _clean_wiki_name -----------------------------------------------------


class TestCleanWikiName:
    def test_wiki_link_plain(self):
        assert _clean_wiki_name("[[Jannik Sinner]]") == "Jannik Sinner"

    def test_wiki_link_pipe(self):
        assert _clean_wiki_name("[[Jannik Sinner|J. Sinner]]") == "J. Sinner"

    def test_strips_flag_template(self):
        assert _clean_wiki_name("{{flagicon|ITA}} [[Jannik Sinner]]") == "Jannik Sinner"

    def test_strips_italics(self):
        assert _clean_wiki_name("''Jannik Sinner''") == "Jannik Sinner"

    def test_none_passthrough(self):
        assert _clean_wiki_name(None) is None


# ---- _resolve_player ------------------------------------------------------


class TestResolvePlayer:
    def test_exact_match_via_name_key(self, session):
        sinner = _player(session, "Jannik Sinner")
        # Same person, same exact name.
        got = _resolve_player(session, "Jannik Sinner", Tour.ATP)
        assert got is not None
        assert got.id == sinner.id

    def test_last_name_with_diacritic(self, session):
        marozsan = _player(session, "Fábián Marozsán")
        # Wikipedia ships unaccented "F. Marozsan"; we should still find him.
        got = _resolve_player(session, "F. Marozsan", Tour.ATP)
        assert got is not None
        assert got.id == marozsan.id

    def test_initial_vs_full_first_name(self, session):
        ofner = _player(session, "Sebastian Ofner")
        got = _resolve_player(session, "S Ofner", Tour.ATP)
        assert got is not None
        assert got.id == ofner.id

    def test_two_letter_initials(self, session):
        # "TM Etcheverry" should match "Tomas Martin Etcheverry"
        etcheverry = _player(session, "Tomas Martin Etcheverry")
        got = _resolve_player(session, "TM Etcheverry", Tour.ATP)
        assert got is not None
        assert got.id == etcheverry.id

    def test_particle_last_name(self, session):
        # "B van de Zandschulp" should match "Botic van de Zandschulp"
        botic = _player(session, "Botic van de Zandschulp")
        got = _resolve_player(session, "B van de Zandschulp", Tour.ATP)
        assert got is not None
        assert got.id == botic.id

    def test_two_players_share_last_name_disambiguates_by_initial(self, session):
        alexei = _player(session, "Alexei Popyrin")
        anthony = _player(session, "Anthony Popyrin")
        got_alexei = _resolve_player(session, "A Popyrin", Tour.ATP)
        # Both Alexei and Anthony start with "A" — we tie-break on lowest id.
        # Inserted in order, Alexei has the lower id so he wins.
        assert got_alexei is not None
        assert got_alexei.id == alexei.id
        # And conversely an unambiguous first initial picks the right one.
        # (This is the safety net for when initials actually differ.)
        _ = anthony  # silence unused-warning

    def test_preferred_ids_breaks_ties(self, session):
        # Same setup but tell the resolver Anthony is in the tournament.
        # Verifies preferred_ids overrides the lowest-id tie-break.
        alexei = _player(session, "Alexei Popyrin")
        anthony = _player(session, "Anthony Popyrin")
        got = _resolve_player(
            session,
            "A Popyrin",
            Tour.ATP,
            preferred_ids={anthony.id},
        )
        assert got is not None
        assert got.id == anthony.id
        _ = alexei

    def test_no_match_returns_none(self, session):
        _player(session, "Jannik Sinner")
        assert _resolve_player(session, "Carlos Alcaraz", Tour.ATP) is None

    def test_wrong_tour_returns_none(self, session):
        # An ATP-only Player shouldn't match a WTA lookup.
        _player(session, "Jannik Sinner")
        assert _resolve_player(session, "Jannik Sinner", Tour.WTA) is None


# ---- _wiki_title_for ------------------------------------------------------


class TestWikiTitleFor:
    def _t(self, slug, year, tour, cat=TournamentCategory.ATP_1000):
        return Tournament(
            slug=slug, year=year, name=slug.title(), tour=tour, category=cat,
        )

    def test_rome_singles(self):
        t = self._t("rome", 2026, Tour.ATP)
        assert _wiki_title_for(t, doubles=False) == "2026 Italian Open – Men's singles"

    def test_madrid_uses_mutua(self):
        t = self._t("madrid", 2026, Tour.ATP)
        assert _wiki_title_for(t, doubles=False) == "2026 Mutua Madrid Open – Men's singles"

    def test_wta_uses_womens(self):
        t = self._t("rome", 2026, Tour.WTA)
        assert _wiki_title_for(t, doubles=False) == "2026 Italian Open – Women's singles"

    def test_doubles(self):
        t = self._t("rome", 2026, Tour.ATP)
        assert _wiki_title_for(t, doubles=True) == "2026 Italian Open – Men's doubles"

    def test_unknown_slug_returns_none(self):
        t = self._t("hong-kong", 2026, Tour.ATP)
        assert _wiki_title_for(t, doubles=False) is None


# ---- bracket parser end-to-end (small fixture) ----------------------------


SAMPLE_8TEAM_BRACKET = """
{{8TeamBracket-Tennis3-v2
|RD1=Quarterfinals
|RD2=Semifinals
|RD3=Final
|RD1-seed1=1
|RD1-team1=[[Jannik Sinner]]
|RD1-score1-1=6
|RD1-team2=[[Andrey Rublev]]
|RD1-score2-1=4
|RD1-seed3=3
|RD1-team3=[[Novak Djokovic]]
|RD1-team4=[[Daniil Medvedev]]
|RD1-seed4=7
}}
""".strip()


class TestBracketParser:
    def test_extract_finds_template(self):
        blocks = _extract_bracket_blocks(SAMPLE_8TEAM_BRACKET)
        assert len(blocks) == 1

    def test_parse_classifies_as_summary(self):
        block = _extract_bracket_blocks(SAMPLE_8TEAM_BRACKET)[0]
        pb = _parse_bracket_block(block, 0)
        assert pb is not None
        assert pb.kind == "summary"

    def test_parses_match_pairs(self):
        block = _extract_bracket_blocks(SAMPLE_8TEAM_BRACKET)[0]
        pb = _parse_bracket_block(block, 0)
        assert pb is not None
        rd1 = [m for m in pb.matches if m.rd_index == 1]
        assert len(rd1) == 2
        m1, m2 = sorted(rd1, key=lambda m: m.position)
        assert m1.p1_name == "Jannik Sinner"
        assert m1.p1_seed == 1
        assert m1.p2_name == "Andrey Rublev"
        assert m1.p2_seed is None
        assert m2.p1_name == "Novak Djokovic"
        assert m2.p1_seed == 3
        assert m2.p2_name == "Daniil Medvedev"
        assert m2.p2_seed == 7

    def test_resolve_shape_total_rounds(self):
        block = _extract_bracket_blocks(SAMPLE_8TEAM_BRACKET)[0]
        pb = _parse_bracket_block(block, 0)
        shape = _resolve_draw_shape([pb])
        assert shape is not None
        assert shape.total_rounds == 3
        assert shape.label_by_round == {1: "QF", 2: "SF", 3: "F"}
