"""api-tennis.com provider.

Endpoints (REST): GET {base_url}/?method=...&APIkey=...
- get_livescore           — currently live matches (includes event_live: "1")
- get_fixtures            — fixtures by date range (date_start, date_stop, YYYY-MM-DD)
- get_events              — event types (Atp Singles, Wta Singles, etc.)
- get_tournaments         — tournament metadata
- get_players             — player profile (?player_key=)
- get_standings           — rankings (?event_type=ATP|WTA)
- get_H2H                 — head-to-head (?first_player_key=&second_player_key=)

This is the only file that should know api-tennis's wire format. Anything
that consumes data from here speaks `LiveMatch`.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.services.live.base import (
    LiveMatch,
    LiveScoresProvider,
    PlayerProfile,
    RankingEntry,
    TournamentMeta,
)


class ApiTennisProvider(LiveScoresProvider):
    name = "api_tennis"

    def __init__(self, api_key: str, base_url: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=15.0)

    async def aclose(self) -> None:
        await self._client.aclose()

    # api-tennis defaults to *venue-local* time for `event_date` /
    # `event_time` unless `timezone=UTC` is passed. We pin it here so
    # every REST endpoint returns UTC, matching the WS contract — without
    # it Rome fixtures arrived as 19:00 (CEST) and got stored as if they
    # were 19:00 UTC, shifting every match by 2h on the frontend.
    _UTC_DEFAULT_PARAMS = {"timezone": "UTC"}

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def _call(self, method: str, **params: Any) -> Any:
        params = {
            "method": method,
            "APIkey": self.api_key,
            **self._UTC_DEFAULT_PARAMS,
            **params,
        }
        r = await self._client.get(f"{self.base_url}/", params=params)
        r.raise_for_status()
        data = r.json()
        if data.get("success") != 1:
            return []
        return data.get("result", []) or []

    async def fetch_live(self) -> list[LiveMatch]:
        rows = await self._call("get_livescore")
        return [self._map(row) for row in rows]

    async def fetch_today(self) -> list[LiveMatch]:
        today = date.today().isoformat()
        rows = await self._call("get_fixtures", date_start=today, date_stop=today)
        return [self._map(row) for row in rows]

    async def fetch_tournaments(self) -> list[TournamentMeta]:
        rows = await self._call("get_tournaments")
        out: list[TournamentMeta] = []
        for r in rows:
            event_type = (r.get("event_type_type") or "")
            tour = self._tour_from_event_type(event_type)
            if not tour:
                continue
            name = (r.get("tournament_name") or "").strip()
            if not name:
                continue
            surface = (r.get("tournament_sourface") or r.get("tournament_surface") or "").strip().lower()
            out.append(
                TournamentMeta(
                    external_id=str(r.get("tournament_key") or ""),
                    name=name,
                    tour=tour,
                    event_type=event_type,
                    surface=surface or None,
                    is_doubles="doubles" in event_type.lower(),
                )
            )
        return out

    @staticmethod
    def _tour_from_event_type(event_type: str) -> str | None:
        """Skip exhibition / junior / mixed / teams — they pollute the catalog."""
        e = event_type.lower()
        skip_markers = ("exhibition", "boys", "girls", "teams", "mixed")
        if any(m in e for m in skip_markers):
            return None
        if "wta" in e or ("itf" in e and "women" in e) or ("challenger" in e and "women" in e):
            return "wta"
        if "atp" in e or ("itf" in e and "men" in e) or ("challenger" in e and "men" in e):
            return "atp"
        return None

    async def fetch_player(self, external_id: str) -> PlayerProfile | None:
        rows = await self._call("get_players", player_key=external_id)
        if not rows:
            return None
        r = rows[0]
        return PlayerProfile(
            external_id=str(r.get("player_key") or external_id),
            name=(r.get("player_name") or "").strip(),
            country_name=(r.get("player_country") or "").strip() or None,
            birth_date=self._parse_dmy(r.get("player_bday")),
            image_url=(r.get("player_logo") or "").strip() or None,
        )

    @staticmethod
    def _parse_dmy(s: str | None) -> date | None:
        """api-tennis returns dates as DD.MM.YYYY (e.g. '22.05.1987')."""
        if not s:
            return None
        try:
            d, m, y = s.strip().split(".")
            return date(int(y), int(m), int(d))
        except (ValueError, AttributeError):
            return None

    async def fetch_rankings(self, tour: str) -> list[RankingEntry]:
        event_type = tour.upper()
        rows = await self._call("get_standings", event_type=event_type)
        out: list[RankingEntry] = []
        for r in rows:
            try:
                rank = int(str(r.get("place") or "").strip())
            except ValueError:
                continue
            try:
                points = int(str(r.get("points") or "").strip()) if r.get("points") else None
            except ValueError:
                points = None
            out.append(
                RankingEntry(
                    rank=rank,
                    points=points,
                    player_name=(r.get("player") or "").strip(),
                    player_external_id=str(r.get("player_key") or "") or None,
                    country_name=(r.get("country") or "").strip() or None,
                    movement=(r.get("movement") or "").strip() or None,
                    tour=tour,
                )
            )
        return out

    # ---- Mapping ------------------------------------------------------------

    def _map(self, row: dict) -> LiveMatch:
        ett = (row.get("event_type_type") or "").lower()
        tname = (row.get("tournament_name") or "")
        tour = self._classify_tour(ett, tname)

        is_doubles = "doubles" in ett or "/" in (row.get("event_first_player") or "")

        # event_live is "1" for live matches per api-tennis docs.
        is_live = str(row.get("event_live") or "").strip() == "1"
        winner_raw = (row.get("event_winner") or "").strip()
        status = self._derive_status(is_live, winner_raw, row.get("event_status"))

        winner: int | None = None
        if winner_raw == "First Player":
            winner = 1
        elif winner_raw == "Second Player":
            winner = 2

        server: int | None = None
        serve_raw = (row.get("event_serve") or "").strip()
        if serve_raw == "First Player":
            server = 1
        elif serve_raw == "Second Player":
            server = 2

        # Build score string from the scores array if present, else the
        # flat event_final_result. scores is the canonical source.
        scores: list[dict] = row.get("scores") or []
        if scores:
            score_str = " ".join(
                self._fmt_set(s.get("score_first"), s.get("score_second"))
                for s in scores
                if s.get("score_first") or s.get("score_second")
            ).strip() or None
            current_set = max(
                (int(s.get("score_set", 0)) for s in scores if str(s.get("score_set", "")).isdigit()),
                default=None,
            )
        else:
            score_str = self._fmt_flat(row.get("event_final_result"))
            current_set = None

        return LiveMatch(
            provider_match_id=str(row.get("event_key") or ""),
            tour=tour,
            tournament_name=(row.get("tournament_name") or "Unknown").strip(),
            tournament_external_id=str(row.get("tournament_key") or "") or None,
            surface=None,  # api-tennis does not return surface on the match row
            round=(row.get("tournament_round") or None),
            player1_name=(row.get("event_first_player") or "").strip() or None,
            player1_external_id=str(row.get("first_player_key") or "") or None,
            player2_name=(row.get("event_second_player") or "").strip() or None,
            player2_external_id=str(row.get("second_player_key") or "") or None,
            score=score_str,
            current_set=current_set,
            current_game=(row.get("event_game_result") or None),
            server=server,
            status=status,
            scheduled_at=self._parse_dt(row.get("event_date"), row.get("event_time")),
            winner=winner,
            is_doubles=is_doubles,
            best_of=5 if "grand slam" in (row.get("tournament_name") or "").lower() and not is_doubles and tour == "atp" else 3,
            raw=row,
        )

    @staticmethod
    def _classify_tour(event_type_type: str, tournament_name: str) -> str:
        """Map api-tennis event_type_type / tournament name → 'atp' | 'wta'.

        api-tennis returns event_type_type values like 'Atp Singles', 'Atp Doubles',
        'Wta Singles', 'Wta Doubles', 'Itf Men Singles', 'Itf Women Singles'. ITF
        tournaments encode gender in the tournament name prefix: M15/M25/M40 for men,
        W15/W35/W50/W60/W75/W100 for women. Challenger Tour is men-only, WTA 125
        is women-only.
        """
        ett = event_type_type.lower()
        if "wta" in ett or ("itf" in ett and "women" in ett):
            return "wta"
        if "atp" in ett or ("itf" in ett and "men" in ett):
            return "atp"

        upper = tournament_name.upper()
        if upper.startswith(("WTA", "W15", "W25", "W35", "W50", "W60", "W75", "W100")):
            return "wta"
        if upper.startswith(("ATP", "M15", "M25", "M40", "CH ", "CHALLENGER")):
            return "atp"
        # Default to atp; the sync layer can correct if we get cross-tour signal later.
        return "atp"

    @staticmethod
    def _fmt_set(first: str | None, second: str | None) -> str:
        """api-tennis encodes tiebreaks as '7.8' meaning '7 games, 8 in tiebreak'.

        We render that as '7(8)' — standard tennis notation. Empty/missing parts
        collapse to '-' so a rendered score never includes a literal None.
        """
        return f"{ApiTennisProvider._fmt_score_part(first)}-{ApiTennisProvider._fmt_score_part(second)}"

    @staticmethod
    def _fmt_score_part(part: str | None) -> str:
        if part is None:
            return ""
        s = str(part).strip()
        if "." in s:
            games, _, tb = s.partition(".")
            games = games.strip()
            tb = tb.strip()
            if tb and tb.isdigit():
                return f"{games}({tb})"
            return games
        return s

    @staticmethod
    def _fmt_flat(score: str | None) -> str | None:
        """event_final_result is sometimes 'X.Y - Z.W X-Y' — apply the same dot rule."""
        if not score:
            return None
        out: list[str] = []
        for chunk in score.strip().split():
            if "-" in chunk:
                a, _, b = chunk.partition("-")
                out.append(ApiTennisProvider._fmt_set(a, b))
            else:
                out.append(chunk)
        return " ".join(out) or None

    @staticmethod
    def _derive_status(is_live: bool, winner_raw: str, status_raw: str | None) -> str:
        s = (status_raw or "").lower()
        if winner_raw:
            if "ret" in s:
                return "retired"
            if "w/o" in s or "walkover" in s:
                return "walkover"
            return "finished"
        if is_live:
            return "live"
        # api-tennis flips `event_live` to "0" during rain/lighting/medical
        # pauses and tags `event_status` with "Interrupted" / "Suspended" /
        # "Delayed". Keep the match visible with its in-progress score
        # rather than letting it fall back to "scheduled" and disappear.
        if "interrupt" in s or "suspend" in s or "delay" in s or "rain" in s or "pause" in s:
            return "suspended"
        if "cancel" in s:
            return "cancelled"
        if "postpon" in s:
            return "postponed"
        return "scheduled"

    @staticmethod
    def _parse_dt(d: str | None, t: str | None) -> datetime | None:
        if not d:
            return None
        d = d.strip()
        try:
            if t and t.strip():
                return datetime.fromisoformat(f"{d}T{t.strip()}")
            return datetime.fromisoformat(d)
        except ValueError:
            return None
