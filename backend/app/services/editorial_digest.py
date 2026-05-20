"""Weekly editorial digest generator.

Collects structured facts about the past tour week — finals played,
seed upsets, tournaments still ongoing — and asks Claude Haiku to
weave them into a 250-300 word narrative paragraph. The model's output
is constrained via `tool_use` so we get a headline + body without
parsing free-form text.

Idempotent: re-running for a week that already has a row is a no-op
unless `force=True`. Safe to invoke from a cron, a backfill script,
or an admin endpoint.

If `ANTHROPIC_API_KEY` is unset the generator logs a warning and
returns None — the cron job and backfill script handle this
gracefully.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlmodel import Session, func, select

from app.models.digest import EditorialDigest
from app.models.match import Match, MatchStatus
from app.models.news import NewsItem
from app.models.player import Player
from app.models.tournament import Tournament, TournamentCategory

log = logging.getLogger("editorial_digest")

# Haiku is plenty for paraphrasing structured facts into a narrative;
# Sonnet/Opus would burn ~30-150× the cost for marginal prose quality.
MODEL_NAME = "claude-haiku-4-5-20251001"

# Categories we treat as "headline" tournaments for the upset filter
# and the "still playing" status pass. 250s and Challengers are skipped
# from these so the prompt isn't drowned by minor-event noise.
_HEADLINE_CATEGORIES = (
    TournamentCategory.GRAND_SLAM,
    TournamentCategory.ATP_1000,
    TournamentCategory.WTA_1000,
    TournamentCategory.ATP_500,
    TournamentCategory.WTA_500,
    TournamentCategory.ATP_FINALS,
    TournamentCategory.WTA_FINALS,
)

# Premier finals — these dominate the digest. Slams + 1000s + 500s +
# year-end Finals. Same set as `_HEADLINE_CATEGORIES`.
_PREMIER_CATEGORIES = _HEADLINE_CATEGORIES

# 250s are reported in a separate "lower tier" block so the prompt
# can list them when there's no premier event happening (early-season
# warm-ups, weeks between Slam swings) without diluting the lead.
_LOWER_TIER_CATEGORIES = (
    TournamentCategory.ATP_250,
    TournamentCategory.WTA_250,
)

# Final round labels — handles short codes (F), human labels (Final),
# and api-tennis verbose forms (anything ending in "final").
_FINAL_ROUNDS_SHORT = {"F", "Final"}

# Rounds where a top-15 player losing is editorially notable. R16 is
# included — losing in the round-of-16 of a Slam is still an upset
# story when the winner is well outside the top tier.
_EARLY_ROUNDS_FOR_UPSET = {"R128", "R64", "R32", "R16"}

# Cap on news items we feed the LLM. 30 is a sweet spot — enough to
# catch the week's storylines without bloating the prompt or letting
# minor player chatter pad the recap. We surface most-recent first.
_NEWS_CAP = 30


def _strip_html(s: str | None) -> str:
    """Crude HTML strip for news summaries. Many sources publish summary
    fields wrapped in <p>, <ul>, <li>, sometimes with trailing "The post …"
    boilerplate. We don't need full HTML parsing — the LLM tolerates a
    bit of noise but appreciates a clean prompt."""
    if not s:
        return ""
    out = re.sub(r"<[^>]+>", " ", s)
    out = re.sub(r"\s+", " ", out).strip()
    # Strip common boilerplate suffixes.
    out = re.sub(
        r"\s*The post\s+.+? appeared first on .+\.?$",
        "", out, flags=re.IGNORECASE,
    )
    return out[:280]  # cap each summary so the prompt doesn't bloat


def _collect_news(session: Session, week_start: date, week_end: date) -> list[dict]:
    """News headlines + summaries from the past 7 days.

    Returns shape: [{source, published_at, title, summary}, ...], most
    recent first, capped at _NEWS_CAP. Past-week window is broad enough
    to catch storylines that broke mid-week before the digest fires;
    same-week-only would miss the Tuesday news drops by the time the
    Monday-of-next-week cron runs.

    Off-court news (withdrawals, injuries, retirements, scandals) lives
    here — none of that is reachable from the match table.
    """
    start_dt = datetime.combine(week_start, time.min)
    end_dt = datetime.combine(week_end, time.max)
    rows = session.exec(
        select(NewsItem)
        .where(
            NewsItem.published_at >= start_dt,
            NewsItem.published_at <= end_dt,
        )
        .order_by(NewsItem.published_at.desc())
        .limit(_NEWS_CAP * 3)  # pull a buffer; dedupe + cap below
    ).all()

    # Light dedup on title — multiple sources cover the same story with
    # near-identical headlines. We don't try to be clever; just drop
    # exact-title repeats.
    seen_titles: set[str] = set()
    out: list[dict] = []
    for n in rows:
        key = (n.title or "").strip().lower()
        if not key or key in seen_titles:
            continue
        seen_titles.add(key)
        out.append({
            "source": n.source,
            "published_at": n.published_at.isoformat(timespec="minutes"),
            "title": n.title.strip(),
            "summary": _strip_html(n.summary),
        })
        if len(out) >= _NEWS_CAP:
            break
    return out


def _normalize_round(raw: str | None) -> str | None:
    """Normalise a round label to a short code (R128/R64/R32/R16/QF/SF/F).

    The DB carries two shapes:
      - Sackmann ingest: short codes already ("R128", "F", "QF" …).
      - api-tennis: verbose, often tournament-prefixed
        ("ATP Rome - 1/64-finals", "Brazzaville - Quarter-finals").

    Returns None when the label doesn't look like a round (e.g. doubles
    rubber, Hopman Cup group stage).
    """
    if not raw:
        return None
    s = raw.strip()
    if s in {"R128", "R64", "R32", "R16", "QF", "SF", "F"}:
        return s
    # Strip "Tournament Name - " prefix so we just have the round token.
    tail = s.rsplit(" - ", 1)[-1].lower().strip()
    if "1/64" in tail:
        return "R128"
    if "1/32" in tail:
        return "R64"
    if "1/16" in tail:
        return "R32"
    if "1/8" in tail:
        return "R16"
    if "quarter" in tail:
        return "QF"
    if "semi" in tail:
        return "SF"
    if tail.rstrip("s") == "final" or tail == "f":
        return "F"
    return None


def monday_of(d: date) -> date:
    """Return the Monday of the ISO week containing `d`."""
    return d - timedelta(days=d.weekday())


@dataclass
class _Tournament:
    slug: str
    year: int
    name: str
    tour: str
    category: str
    surface: str | None


@dataclass
class _Final:
    tournament_id: int
    tournament: _Tournament
    champion: str
    champion_slug: str
    runner_up: str | None
    runner_up_slug: str | None
    score: str | None


@dataclass
class _Upset:
    tournament: _Tournament
    round: str
    winner: str
    winner_slug: str
    winner_rank: int | None
    loser: str
    loser_slug: str
    loser_rank: int


def collect_week_facts(session: Session, week_start: date) -> dict:
    """Pull every fact for the week into a JSON-serialisable dict.

    Returned shape is what gets fed into the prompt verbatim. We dataclass
    the rows internally for type safety, then `_to_dict` them at the end
    so the prompt builder can format them with simple dict access.
    """
    week_end = week_start + timedelta(days=6)
    start_dt = datetime.combine(week_start, time.min)
    end_dt = datetime.combine(week_end, time.max)

    # Lookup tables keyed by id — built once, used for every match row.
    tournaments = {
        t.id: t
        for t in session.exec(select(Tournament)).all()
    }
    players = {
        p.id: p
        for p in session.exec(select(Player)).all()
    }

    def _t(tid: int | None) -> _Tournament | None:
        t = tournaments.get(tid) if tid else None
        if not t:
            return None
        return _Tournament(
            slug=t.slug, year=t.year, name=t.name,
            tour=_str_enum(t.tour),
            category=_str_enum(t.category),
            surface=_str_enum(t.surface) if t.surface else None,
        )

    def _p(pid: int | None) -> tuple[str, str] | None:
        p = players.get(pid) if pid else None
        if not p:
            return None
        return p.full_name, p.slug

    finals_raw: list[_Final] = []
    lower_finals_raw: list[_Final] = []
    upsets: list[_Upset] = []
    premier_values = {c.value for c in _PREMIER_CATEGORIES}
    lower_values = {c.value for c in _LOWER_TIER_CATEGORIES}

    week_matches = session.exec(
        select(Match)
        .where(
            Match.status == MatchStatus.FINISHED,
            Match.is_doubles == False,  # noqa: E712 — SQLModel needs ==
            Match.scheduled_at >= start_dt,
            Match.scheduled_at <= end_dt,
        )
    ).all()

    for m in week_matches:
        normalized = _normalize_round(m.round)
        is_final = normalized == "F"
        t = _t(m.tournament_id)
        if not t:
            continue

        # Finals — bucketed by tier. We drop walkover/retirement finals
        # (rare, lower editorial value).
        if is_final and m.winner_id:
            target = (
                finals_raw if t.category in premier_values
                else lower_finals_raw if t.category in lower_values
                else None
            )
            if target is not None:
                winner = _p(m.winner_id)
                loser_id = (
                    m.player2_id if m.winner_id == m.player1_id else m.player1_id
                )
                loser = _p(loser_id)
                if winner:
                    target.append(_Final(
                        tournament_id=m.tournament_id,
                        tournament=t,
                        champion=winner[0], champion_slug=winner[1],
                        runner_up=loser[0] if loser else None,
                        runner_up_slug=loser[1] if loser else None,
                        score=m.score,
                    ))

        # Upsets: top-15 player losing to outside-top-50 in R128–R16 of a
        # headline event. We use current_rank as the proxy — seeds are NULL
        # for most tournaments and Sackmann ingest doesn't populate them.
        # For 2026 backfill weeks the rank approximation is close enough
        # (rank movement on this scale is rare in a year).
        if (
            t.category in {c.value for c in _HEADLINE_CATEGORIES}
            and normalized in _EARLY_ROUNDS_FOR_UPSET
        ):
            if m.winner_id == m.player1_id:
                loser_id, winner_id = m.player2_id, m.player1_id
            elif m.winner_id == m.player2_id:
                loser_id, winner_id = m.player1_id, m.player2_id
            else:
                loser_id = winner_id = None
            loser_player = players.get(loser_id) if loser_id else None
            winner_player = players.get(winner_id) if winner_id else None
            if (
                loser_player and winner_player
                and loser_player.current_rank is not None
                and loser_player.current_rank <= 15
                and (winner_player.current_rank is None
                     or winner_player.current_rank > 50)
            ):
                upsets.append(_Upset(
                    tournament=t, round=normalized,
                    winner=winner_player.full_name,
                    winner_slug=winner_player.slug,
                    winner_rank=winner_player.current_rank,
                    loser=loser_player.full_name,
                    loser_slug=loser_player.slug,
                    loser_rank=loser_player.current_rank,
                ))

    # Headline tournaments still active at week-end or starting in the
    # coming week — fuel the "what's coming next" closer. Inferred from
    # the match table because Tournament.start_date / end_date are NULL
    # for most non-Slam events in the catalog.
    next_window_start = end_dt + timedelta(seconds=1)
    next_window_end = end_dt + timedelta(days=10)
    upcoming_match_rows = session.exec(
        select(Match.tournament_id, func.min(Match.scheduled_at))
        .where(
            Match.scheduled_at >= next_window_start,
            Match.scheduled_at <= next_window_end,
            Match.is_doubles == False,  # noqa: E712
        )
        .group_by(Match.tournament_id)
    ).all()
    headline_values = {c.value for c in _HEADLINE_CATEGORIES}
    ongoing = []
    for tid, first_match_at in upcoming_match_rows:
        t = tournaments.get(tid)
        if not t:
            continue
        cat_value = _str_enum(t.category)
        if cat_value not in headline_values:
            continue
        ongoing.append({
            "slug": t.slug, "year": t.year, "name": t.name,
            "tour": _str_enum(t.tour),
            "category": cat_value,
            "surface": _str_enum(t.surface) if t.surface else None,
            "starts": first_match_at.date().isoformat() if first_match_at else None,
        })
    ongoing.sort(key=lambda x: (x["starts"] or "9999", x["name"]))

    # Drop tournaments that produced more than one "F" match in the
    # week — a real tournament has exactly one singles final, and
    # multiple Fs almost always signal a categorization bug (e.g. a
    # W125 event tagged as ATP_1000 Paris in our catalog). Better to
    # skip the suspect tournament than feed the LLM dirty data and
    # have it confabulate four-final formats.
    def _dedup_clean(finals_in: list[_Final]) -> list[_Final]:
        by_tid: dict[int, list[_Final]] = {}
        for f in finals_in:
            by_tid.setdefault(f.tournament_id, []).append(f)
        return [fs[0] for fs in by_tid.values() if len(fs) == 1]

    finals = _dedup_clean(finals_raw)
    lower_finals = _dedup_clean(lower_finals_raw)

    # Sort finals + upsets by tournament tier (slams first), then by name.
    _tier_order = {c.value: i for i, c in enumerate(_HEADLINE_CATEGORIES)}
    finals.sort(key=lambda f: (
        _tier_order.get(f.tournament.category, 99), f.tournament.name,
    ))
    lower_finals.sort(key=lambda f: (f.tournament.tour, f.tournament.name))
    upsets.sort(key=lambda u: (
        _tier_order.get(u.tournament.category, 99), u.loser_rank,
    ))

    payload = {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "finals": [_final_to_dict(f) for f in finals],
        "lower_tier_finals": [_final_to_dict(f) for f in lower_finals],
        "upsets": [_upset_to_dict(u) for u in upsets[:6]],  # cap noise
        "ongoing": ongoing,
        # Headlines + summaries from our news feed for the same week.
        # Off-court stories (withdrawals, injuries, retirements,
        # protests) live here — invisible to the match-table.
        "news": _collect_news(session, week_start, week_end),
    }
    # LINKS table: every internal URL the model is allowed to reference,
    # keyed by the prose label we want shown. Persisted in source_json so
    # an audit run can reconstruct what the model was offered.
    payload["links"] = _collect_links_table(payload)
    return payload


def _final_to_dict(f: _Final) -> dict:
    return {
        "tournament": f.tournament.name,
        "tournament_slug": f.tournament.slug,
        "year": f.tournament.year,
        "tour": f.tournament.tour,
        "category": f.tournament.category,
        "surface": f.tournament.surface,
        "champion": f.champion,
        "champion_slug": f.champion_slug,
        "runner_up": f.runner_up,
        "runner_up_slug": f.runner_up_slug,
        "score": f.score,
    }


def _upset_to_dict(u: _Upset) -> dict:
    return {
        "tournament": u.tournament.name,
        "tournament_slug": u.tournament.slug,
        "year": u.tournament.year,
        "tour": u.tournament.tour,
        "category": u.tournament.category,
        "round": u.round,
        "winner": u.winner, "winner_slug": u.winner_slug,
        "winner_rank": u.winner_rank,
        "loser": u.loser, "loser_slug": u.loser_slug,
        "loser_rank": u.loser_rank,
    }


def _collect_links_table(facts: dict) -> dict:
    """Build the {players, tournaments, rivalries} table the model uses to
    render internal links. Every URL here is constructed from a slug we
    already trust (Sackmann ingest, Wikipedia catalog, or live consumer);
    the model is forbidden from inventing URLs outside this list.

    Returns a dict shaped:
        {
          "players":     [{"name": "...", "url": "/players/..."}, ...],
          "tournaments": [{"label": "2026 Madrid (ATP)", "url": "..."}, ...],
          "rivalries":   [{"label": "Sinner vs Zverev", "url": "/h2h/..."}],
        }

    Order is stable (input order, deduped) so the prompt is deterministic
    for a given week's facts.
    """
    players: dict[str, str] = {}
    tournaments: dict[str, str] = {}
    rivalries: dict[str, str] = {}

    def _add_player(name: str | None, slug: str | None) -> None:
        if name and slug and name not in players:
            players[name] = f"/players/{slug}"

    def _add_tournament(
        year: int | None, name: str | None,
        tour: str | None, slug: str | None,
    ) -> None:
        if not (name and tour and slug):
            return
        label = f"{year} {name} ({tour.upper()})" if year else f"{name} ({tour.upper()})"
        if label not in tournaments:
            tournaments[label] = f"/tournaments/{tour}/{slug}"

    def _add_rivalry(
        p1_name: str | None, p1_slug: str | None,
        p2_name: str | None, p2_slug: str | None,
    ) -> None:
        if not (p1_name and p1_slug and p2_name and p2_slug):
            return
        # Canonical URL uses alphabetised slug order — both directions
        # resolve at the API level, but the model should always emit
        # the same string for the same pair.
        a, b = sorted([p1_slug, p2_slug])
        url = f"/h2h/{a}-vs-{b}"
        # Label uses last names; the model will adapt the surrounding
        # prose ("rivalry", "head-to-head", "meeting") on its own.
        last_a = p1_name.split()[-1] if p1_slug == a else p2_name.split()[-1]
        last_b = p2_name.split()[-1] if p1_slug == a else p1_name.split()[-1]
        label = f"{last_a} vs {last_b}"
        if label not in rivalries:
            rivalries[label] = url

    for f in facts.get("finals", []) + facts.get("lower_tier_finals", []):
        _add_player(f.get("champion"), f.get("champion_slug"))
        _add_player(f.get("runner_up"), f.get("runner_up_slug"))
        _add_tournament(
            f.get("year"), f.get("tournament"),
            f.get("tour"), f.get("tournament_slug"),
        )
        _add_rivalry(
            f.get("champion"), f.get("champion_slug"),
            f.get("runner_up"), f.get("runner_up_slug"),
        )
    for u in facts.get("upsets", []):
        _add_player(u.get("winner"), u.get("winner_slug"))
        _add_player(u.get("loser"), u.get("loser_slug"))
        _add_tournament(
            u.get("year"), u.get("tournament"),
            u.get("tour"), u.get("tournament_slug"),
        )
    for o in facts.get("ongoing", []):
        _add_tournament(o.get("year"), o.get("name"), o.get("tour"), o.get("slug"))

    return {
        "players": [{"name": n, "url": u} for n, u in players.items()],
        "tournaments": [{"label": l, "url": u} for l, u in tournaments.items()],
        "rivalries": [{"label": l, "url": u} for l, u in rivalries.items()],
    }


def _str_enum(v) -> str:
    """Normalise an enum-or-string field to its string value. SQLModel
    sometimes hydrates the field as the raw string, sometimes as the
    Enum instance, depending on whether the column came in through ORM
    or a raw select."""
    if v is None:
        return ""
    return v.value if hasattr(v, "value") else str(v)


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------


SYSTEM_PROMPT = """You are the editorial voice of Mobtennis, a tennis fan site.
You write weekly recaps of professional tennis (ATP + WTA combined).

House style:
- Cover only what the supplied facts mention. Do not invent matches, scores, players, tournament names, or formats.
- THREE input blocks carry first-class facts: `Finals`, `Upsets`, and `News`. The `News` block is a digest of headlines from our wire feed — it surfaces stories the match table cannot tell on its own (withdrawals, injuries, retirements, protests, controversies, off-court developments). Treat news items as verified facts the same way you treat finals.
- Lead with the single most consequential story of the week. Decision order:
    1. A withdrawal / injury / retirement / scandal involving a top-10 player and an upcoming Slam or 1000 — promote to the lead even when a Slam final happened the same week, IF the news is clearly more consequential.
    2. Slam result > 1000 final > major upset > 500 final > 250 final.
    3. Other news headlines.
- The primary match block (`Finals` — Slams, 1000s, 500s, year-end Finals) should still dominate the prose when there are premier finals — at minimum 50%% of the paragraph when present. The remainder rounds in news context, upsets, and one closer sentence on what's next.
- The `Lower-tier finals` block (250s) is supporting context only. Use it briefly to round out the week, never as the lead. If the primary block is empty (a quiet warm-up week), the 250 titles or news headlines can take the lead.
- One flowing paragraph. No bullet points, no headers, no sub-paragraphs.
- 220-300 words.
- Present-tense for results that happened this week. Future-tense for what's next.
- Mention 4-7 players by full name on first reference, last name thereafter.
- Energetic but factual. Don't overclaim — phrases like "stunning", "dominant", "ruthless" should be earned by the data, not used as filler.
- Close with one sentence on what's coming next week (use the `ongoing` block for this).
- Do NOT invent matches, scores, players, or tournament names.
- Do NOT mention any data point not in the supplied facts.
- Do NOT use the words "AI" or "digest" or refer to yourself.

EDITORIAL NOTES:
- If the user prompt contains an `EDITORIAL NOTES` section, treat those facts as verified human-supplied context. Weave them naturally into the recap when the prose mentions the related player, tournament, or event. Notes are not inventions: they are additional truths to include.
- Do not invent any other context beyond the supplied facts + notes.

INTERNAL LINKS:
- The user prompt ends with a `LINKS` table listing every internal URL you may reference (players, tournaments, head-to-head pages). Use them as markdown links — `[Display text](/path)` — inline in the body prose.
- Link the FIRST mention of each player and each tournament that appears in the LINKS table. On subsequent mentions, use plain prose (last name only for players is fine).
- You MAY link a "<player> vs <player>" or "rivalry" phrase to a `/h2h/...` URL when the surrounding sentence is explicitly about the head-to-head, but it's optional.
- The URL inside the parentheses MUST be copied VERBATIM from the LINKS table. Do not shorten it, abbreviate it, or modify it in any way. If you abbreviate a player's name in the display text (e.g. "Dino Prizmic" → "D. Prizmic"), the URL must still be the full one shown in LINKS (`/players/dino-prizmic`, NOT `/players/d-prizmic`).
- If a player or tournament isn't in the LINKS table, mention them without any link. NEVER fabricate a URL.
- The headline is plain text, never markdown. Markdown links go in the body only.

The headline is a punchy one-liner under 80 characters — newspaper style, no clickbait."""


def _build_user_prompt(facts: dict) -> str:
    def _format_final(f: dict) -> str:
        score = f" {f['score']}" if f["score"] else ""
        ru = f", def. {f['runner_up']}" if f["runner_up"] else ""
        cat = f["category"].replace("_", " ").upper()
        return (
            f"  - {f['year']} {f['tournament']} ({f['tour'].upper()}, {cat}"
            + (f", {f['surface']}" if f["surface"] else "")
            + f"): {f['champion']}{ru}{score}"
        )

    lines = [
        f"Week: {facts['week_start']} to {facts['week_end']}.",
        "",
        "Finals (PRIMARY — Slams, 1000s, 500s, year-end Finals):",
    ]
    if not facts["finals"]:
        lines.append("  (no premier finals this week)")
    for f in facts["finals"]:
        lines.append(_format_final(f))
    lines.append("")
    lines.append(
        "Lower-tier finals (250s — supporting context, do not lead with these "
        "unless the primary block is empty):"
    )
    if not facts.get("lower_tier_finals"):
        lines.append("  (none)")
    for f in facts.get("lower_tier_finals", []):
        lines.append(_format_final(f))
    lines.append("")
    lines.append(
        "Notable upsets (top-15 player losing in R128/R64/R32/R16 of a "
        "Slam, 500-tier, or 1000-tier event):"
    )
    if not facts["upsets"]:
        lines.append("  (none of note)")
    for u in facts["upsets"]:
        wr = f"ranked #{u['winner_rank']}" if u["winner_rank"] is not None else "unranked"
        lines.append(
            f"  - {u['tournament']} {u['round']}: {u['winner']} ({wr}) def. "
            f"{u['loser']} (ranked #{u['loser_rank']})"
        )
    lines.append("")
    if facts.get("news"):
        lines.append("")
        lines.append(
            "News headlines from this week — off-court stories the match "
            "table cannot tell. Treat these as verified facts. A "
            "consequential story here (e.g. a top-10 withdrawal, an "
            "injury, a retirement) can outrank a 1000-tier result for "
            "the lead. Multiple headlines about the same story signal "
            "its importance:"
        )
        for n in facts["news"]:
            lines.append(
                f"  - [{n['published_at']} {n['source']}] {n['title']}"
                + (f"\n      {n['summary']}" if n.get("summary") else "")
            )
    lines.append("")
    lines.append("Tournaments active at week-end or starting next week:")
    if not facts["ongoing"]:
        lines.append("  (none of headline tier)")
    for t in facts["ongoing"]:
        cat = t["category"].replace("_", " ").upper()
        when = f"first match {t['starts']}" if t["starts"] else ""
        lines.append(
            f"  - {t['year']} {t['name']} ({t['tour'].upper()}, {cat}"
            + (f", {t['surface']}" if t["surface"] else "")
            + f"): {when}"
        )
    if facts.get("editorial_notes"):
        lines.append("")
        lines.append(
            "EDITORIAL NOTES — verified facts to weave into the recap "
            "where relevant. Treat these as truths, not the model's "
            "own additions:"
        )
        for note in facts["editorial_notes"]:
            lines.append(f"  - {note}")
    lines.append("")
    lines.append("LINKS — use these markdown links verbatim when mentioning the corresponding entity. Do not invent URLs.")
    links = facts.get("links", {})
    if links.get("players"):
        lines.append("Players:")
        for p in links["players"]:
            lines.append(f"  - [{p['name']}]({p['url']})")
    if links.get("tournaments"):
        lines.append("Tournaments:")
        for t in links["tournaments"]:
            lines.append(f"  - [{t['label']}]({t['url']})")
    if links.get("rivalries"):
        lines.append("Rivalries (optional — use only when the prose is explicitly about the head-to-head):")
        for r in links["rivalries"]:
            lines.append(f"  - [{r['label']}]({r['url']})")
    return "\n".join(lines)


_TOOL_SPEC = {
    "name": "submit_digest",
    "description": "Submit the final headline and body for the weekly tennis digest.",
    "input_schema": {
        "type": "object",
        "properties": {
            "headline": {
                "type": "string",
                "description": "Newspaper-style headline, under 80 characters.",
            },
            "body": {
                "type": "string",
                "description": (
                    "One paragraph, 220-300 words. No newlines mid-paragraph. "
                    "Inline markdown links of the form [Display text](/path) "
                    "are allowed and expected — use the exact URLs from the "
                    "LINKS section of the user prompt to anchor first mentions "
                    "of each player and tournament. No other markdown."
                ),
            },
        },
        "required": ["headline", "body"],
    },
}


def _call_claude(facts: dict) -> tuple[str, str] | None:
    """Return (headline, body) or None if the call fails / API key
    missing. Caller decides whether to skip or raise."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.warning("ANTHROPIC_API_KEY not set — skipping digest generation")
        return None

    # Lazy import — keeps the module importable on machines without the
    # SDK installed (e.g. CI nodes that only run schema checks).
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    user_prompt = _build_user_prompt(facts)

    try:
        resp = client.messages.create(
            model=MODEL_NAME,
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            tools=[_TOOL_SPEC],
            tool_choice={"type": "tool", "name": "submit_digest"},
            messages=[{"role": "user", "content": user_prompt}],
        )
    except Exception:
        log.exception("Claude call failed for week %s", facts.get("week_start"))
        return None

    # Tool-use response: walk content blocks for the tool_use block we
    # forced via tool_choice. There should be exactly one.
    for block in resp.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "submit_digest":
            payload = block.input
            headline = (payload.get("headline") or "").strip()
            body = (payload.get("body") or "").strip()
            if headline and body:
                return headline, body
    log.warning("Claude returned no usable tool_use block for week %s", facts["week_start"])
    return None


_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def sanitize_body_links(body: str, links: dict) -> str:
    """Strip any markdown link whose URL isn't in the trusted LINKS table.
    Replaces the link with its plain display text so the prose still reads.

    Belt-and-suspenders against the model abbreviating both a name and
    its URL together (e.g. emitting "[D. Prizmic](/players/d-prizmic)"
    when the real slug is `dino-prizmic`). The system prompt forbids
    this, but the cost of a 404 is high enough to warrant a check.
    """
    allowed: set[str] = set()
    for bucket in ("players", "tournaments", "rivalries"):
        for entry in links.get(bucket, []):
            url = entry.get("url")
            if url:
                allowed.add(url)

    def replace(m: re.Match) -> str:
        text, href = m.group(1), m.group(2)
        return m.group(0) if href in allowed else text

    return _MD_LINK_RE.sub(replace, body)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def generate_digest(
    session: Session,
    week_start: date,
    *,
    force: bool = False,
    editorial_notes: list[str] | None = None,
) -> EditorialDigest | None:
    """Top-level entry: collect facts, call Claude, persist row.

    `editorial_notes` is an optional list of verified human-supplied
    facts to weave into the recap — milestones, records, retirements,
    or anything the underlying match data can't tell the model on its
    own. Passed verbatim to the prompt as "EDITORIAL NOTES" and stored
    in `source_json` for audit.

    Returns the saved row, or the existing row if `force=False` and one
    already exists for the week, or None on LLM failure / empty week.
    """
    week_start = monday_of(week_start)

    existing = session.exec(
        select(EditorialDigest).where(EditorialDigest.week_start == week_start)
    ).first()
    if existing and not force:
        return existing

    facts = collect_week_facts(session, week_start)
    if editorial_notes:
        facts["editorial_notes"] = list(editorial_notes)
    if (
        not facts["finals"]
        and not facts.get("lower_tier_finals")
        and not facts["upsets"]
        and not facts["ongoing"]
        and not facts.get("editorial_notes")
        and not facts.get("news")
    ):
        log.info("No newsworthy facts for week %s — skipping", week_start)
        return None

    result = _call_claude(facts)
    if result is None:
        return None
    headline, body = result
    body = sanitize_body_links(body, facts.get("links", {}))

    if existing and force:
        existing.headline = headline
        existing.body_md = body
        existing.source_json = json.dumps(facts)
        existing.model_name = MODEL_NAME
        existing.generated_at = datetime.utcnow()
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    row = EditorialDigest(
        week_start=week_start,
        headline=headline,
        body_md=body,
        source_json=json.dumps(facts),
        model_name=MODEL_NAME,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row
