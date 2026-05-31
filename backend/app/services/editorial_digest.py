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


def _collect_news(session: Session, start_dt: datetime, end_dt: datetime) -> list[dict]:
    """News headlines + summaries in [start_dt, end_dt].

    Returns shape: [{source, published_at, title, summary}, ...], most
    recent first, capped at _NEWS_CAP. The window is whatever the
    caller passes — typically the digest's `[period_start, period_end]`
    so an ad-hoc Wednesday digest only covers news since the last one.

    Off-court news (withdrawals, injuries, retirements, scandals) lives
    here — none of that is reachable from the match table.
    """
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
            "url": n.source_url,
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


def collect_period_facts(
    session: Session, period_start: datetime, period_end: datetime,
) -> dict:
    """Pull every fact for the [period_start, period_end] window into a
    JSON-serialisable dict.

    Window is arbitrary — a Monday cron typically passes a full week,
    an ad-hoc Wednesday call passes "since last digest" (could be a
    couple of days). The prompt downstream adapts to the actual length.
    """
    start_dt = period_start
    end_dt = period_end

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
        # Main-draw final only — short code "F" from Sackmann + Wikipedia.
        # _normalize_round would collapse "ATP French Open - Final" (a
        # qualifying-bracket final at api-tennis) to "F", which would
        # have produced 16 spurious "RG final" entries in the digest's
        # facts during qualifying weeks.
        is_final = m.round == "F"
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
        # ISO timestamps so the prompt can phrase the window precisely
        # (e.g. "since Tuesday morning" for a Wed mid-week digest).
        "period_start": period_start.isoformat(timespec="minutes"),
        "period_end": period_end.isoformat(timespec="minutes"),
        # Anchor date for URL slug — derived in the caller; kept as a
        # convenience field on the facts.
        "anchor_date": period_end.date().isoformat(),
        "finals": [_final_to_dict(f) for f in finals],
        "lower_tier_finals": [_final_to_dict(f) for f in lower_finals],
        "upsets": [_upset_to_dict(u) for u in upsets[:6]],  # cap noise
        "ongoing": ongoing,
        # Headlines + summaries from our news feed for the same window.
        # Off-court stories (withdrawals, injuries, retirements,
        # protests) live here — invisible to the match-table.
        "news": _collect_news(session, period_start, period_end),
    }
    # LINKS table: every internal URL the model is allowed to reference,
    # keyed by the prose label we want shown. Persisted in source_json so
    # an audit run can reconstruct what the model was offered.
    payload["links"] = _collect_links_table(payload)
    return payload


# Backwards-compat shim: a few scripts still call collect_week_facts
# with a Monday date. Translate to the new period-based API.
def collect_week_facts(session: Session, week_start: date) -> dict:
    period_start = datetime.combine(week_start, time.min)
    period_end = datetime.combine(week_start + timedelta(days=6), time.max)
    return collect_period_facts(session, period_start, period_end)


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


SYSTEM_PROMPT = """You are the editorial voice of Mob Tennis, a tennis fan site.
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

CAMPAIGN BRIEFS:
- Alongside the body, return 3-5 Google Ads campaign briefs in the `campaign_briefs` field of the tool call.
- Each brief targets ONE story or theme that tennis fans will likely search for in the coming 1-2 weeks. Pick stories with the highest expected search volume: Slam draws / results, top-10 results, injuries, withdrawals, retirements, ranking-shift narratives.
- For each brief, generate KEYWORDS (search queries fans type), RSA AD HEADLINES (each ≤ 30 chars), RSA AD DESCRIPTIONS (each ≤ 90 chars), and a LANDING_PATH (internal mob.tennis URL from the LINKS section — most-specific page for the topic).
- Stay strictly within the supplied facts. No invented stories, scores, players, or tournament names. Same rules as the body.
- Ad copy goal: drive a click. Honest, factual, no clickbait, no superlatives the data doesn't support. Mention mob.tennis or the value (free, no sign-up, live scores) in at least one headline.

NEWS SOURCES:
- The recap is editorial paraphrase, not original reporting. When a sentence's facts came primarily from one of the supplied News headlines (an injury, a withdrawal, a press conference, an off-court development), record the source in the `news_sources` tool field so readers can read the original article.
- Only include sources you actually drew from. If the recap leans on 3 headlines, list 3. If the week was all match results and you didn't lean on any news, return an empty list.
- Each source is `{title, url, source}` — copy these verbatim from the News block. Do NOT invent URLs or rewrite titles.

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

    # Period heading: prefer the explicit window, fall back to the
    # legacy week_start/week_end keys for pre-windowed source_json
    # rows we might rerun the prompt against.
    ps = facts.get("period_start") or facts.get("week_start")
    pe = facts.get("period_end") or facts.get("week_end")
    lines = [
        f"Coverage window: {ps} to {pe}.",
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
            "its importance. Each item ends with a URL — when you write a "
            "sentence whose facts came primarily from one of these "
            "headlines, list its URL in the `news_sources` tool field so "
            "readers can follow the original reporting:"
        )
        for n in facts["news"]:
            lines.append(
                f"  - [{n['published_at']} {n['source']}] {n['title']}"
                + (f"\n      {n['summary']}" if n.get("summary") else "")
                + (f"\n      URL: {n['url']}" if n.get("url") else "")
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
    "description": (
        "Submit the final headline and body for the weekly tennis digest, "
        "PLUS 3-5 Google Ads campaign briefs derived from the week's stories."
    ),
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
            "news_sources": {
                "type": "array",
                "description": (
                    "Source-article citations. List ONLY the News headlines "
                    "whose facts you actually leaned on in writing the body. "
                    "Copy `title`, `url`, and `source` verbatim from the "
                    "News block of the user prompt. Empty list is fine when "
                    "the recap is driven by match results alone."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "url": {"type": "string"},
                        "source": {"type": "string"},
                    },
                    "required": ["title", "url", "source"],
                },
            },
            "campaign_briefs": {
                "type": "array",
                "description": (
                    "3-5 Google Ads campaign briefs to drive search traffic "
                    "to mob.tennis this week. Each brief targets ONE story "
                    "or theme that tennis fans are likely to search for in "
                    "the next 1-2 weeks. Pick stories with clear search "
                    "intent (Slam draw, big result, injury/withdrawal, "
                    "ranking shift). DO NOT invent stories — every brief "
                    "must derive from the supplied facts."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "theme": {
                            "type": "string",
                            "description": (
                                "Short label for the campaign (≤ 50 chars). "
                                "e.g. 'Alcaraz Wimbledon withdrawal'."
                            ),
                        },
                        "rationale": {
                            "type": "string",
                            "description": (
                                "1-2 sentences on why fans will search this "
                                "topic in the coming 2 weeks. Reference the "
                                "supplied facts."
                            ),
                        },
                        "keywords": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "5-15 search terms or phrases. Each ≤ 80 "
                                "chars. Mix exact player names, event names, "
                                "and natural-language queries fans actually "
                                "type. No hashtags, no quotes."
                            ),
                        },
                        "ad_headlines": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "5-10 Google Ads RSA headlines. EACH ≤ 30 "
                                "characters (Google Ads will reject longer). "
                                "Vary the angle: one with the player name, "
                                "one with the result, one with the site "
                                "promise, etc."
                            ),
                        },
                        "ad_descriptions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "2-4 Google Ads RSA descriptions. EACH ≤ 90 "
                                "characters. Should expand on the headline "
                                "and end with a value prop (live scores, "
                                "free, no signup, etc.)."
                            ),
                        },
                        "landing_path": {
                            "type": "string",
                            "description": (
                                "Internal mob.tennis path the ad should land "
                                "on. MUST start with '/'. Pick the most "
                                "relevant page from the LINKS section of the "
                                "user prompt — usually a /players/<slug>, "
                                "/tournaments/<tour>/<slug>, or "
                                "/digest/<week_start>. Default to the "
                                "current digest URL if no better fit exists."
                            ),
                        },
                    },
                    "required": [
                        "theme", "rationale", "keywords",
                        "ad_headlines", "ad_descriptions", "landing_path",
                    ],
                },
            },
        },
        "required": ["headline", "body", "campaign_briefs", "news_sources"],
    },
}


def _call_claude(facts: dict) -> tuple[str, str, list[dict], list[dict]] | None:
    """Return (headline, body, campaign_briefs, news_sources) or None
    if the call fails / API key missing. Caller decides whether to
    skip or raise.

    `campaign_briefs` and `news_sources` are always lists — empty if
    the model declined or the field is malformed."""
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
            # Bumped from 1500 — campaign_briefs adds ~600-1000 output
            # tokens (3-5 briefs × ~150 tokens each).
            max_tokens=3000,
            system=SYSTEM_PROMPT,
            tools=[_TOOL_SPEC],
            tool_choice={"type": "tool", "name": "submit_digest"},
            messages=[{"role": "user", "content": user_prompt}],
        )
    except Exception:
        log.exception("Claude call failed for window %s",
                      facts.get("anchor_date") or facts.get("week_start"))
        return None

    # Tool-use response: walk content blocks for the tool_use block we
    # forced via tool_choice. There should be exactly one.
    for block in resp.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "submit_digest":
            payload = block.input
            headline = (payload.get("headline") or "").strip()
            body = (payload.get("body") or "").strip()
            briefs_raw = payload.get("campaign_briefs") or []
            if not isinstance(briefs_raw, list):
                briefs_raw = []
            # Build the set of trusted landing URLs from the LINKS
            # table (player + tournament + h2h URLs we offered) PLUS
            # this digest's own URL as a safe default.
            links = facts.get("links", {}) or {}
            allowed: set[str] = set()
            for bucket in ("players", "tournaments", "rivalries"):
                for entry in links.get(bucket, []):
                    u = entry.get("url")
                    if u:
                        allowed.add(u)
            digest_url = (
                f"/digest/{facts.get('anchor_date') or facts.get('week_start', '')}"
            )
            allowed.add(digest_url)
            briefs = _validate_campaign_briefs(
                briefs_raw,
                allowed_urls=allowed,
                fallback_url=digest_url,
            )
            # Validate news_sources against the URLs we offered — guards
            # against the model inventing a URL or paraphrasing the
            # title. The URL must match exactly (after stripping) one of
            # the news items we passed in.
            news_offered = {
                (n.get("url") or "").strip(): n
                for n in (facts.get("news") or [])
                if n.get("url")
            }
            news_raw = payload.get("news_sources") or []
            news_sources: list[dict] = []
            if isinstance(news_raw, list):
                seen_urls: set[str] = set()
                for item in news_raw:
                    if not isinstance(item, dict):
                        continue
                    url = (item.get("url") or "").strip()
                    if not url or url in seen_urls or url not in news_offered:
                        continue
                    seen_urls.add(url)
                    # Trust the offered values over what the LLM repeated
                    # back — model paraphrases sometimes drift a few chars.
                    canon = news_offered[url]
                    news_sources.append({
                        "title": canon.get("title", item.get("title", "")),
                        "url": url,
                        "source": canon.get("source", item.get("source", "")),
                    })
            if headline and body:
                return headline, body, briefs, news_sources
    log.warning(
        "Claude returned no usable tool_use block for window %s",
        facts.get("anchor_date") or facts.get("week_start"),
    )
    return None


# Google Ads RSA hard limits — anything over is auto-rejected by the
# UI on import. We truncate rather than drop so a too-long item still
# offers value, and we cap the brief count to keep storage / UI clean.
_MAX_HEADLINE_CHARS = 30
_MAX_DESCRIPTION_CHARS = 90
_MAX_KEYWORD_CHARS = 80
_MAX_BRIEFS = 6


def _word_truncate(s: str, limit: int) -> str:
    """Truncate `s` to at most `limit` chars, breaking on a word boundary
    rather than mid-word. Used for ad headlines/descriptions where
    "Alcaraz Withdraws From Roland " mid-word looks unprofessional in
    a search ad. Returns the original string when already in-budget."""
    s = s.strip()
    if len(s) <= limit:
        return s
    cut = s[:limit]
    # Walk back to the last space; drop the partial word.
    last_space = cut.rfind(" ")
    if last_space >= int(limit * 0.6):
        return cut[:last_space].rstrip(" ,.;:-")
    # No reasonable word boundary — drop the whole headline.
    return ""


def _validate_campaign_briefs(
    raw: list, *, allowed_urls: set[str] | None = None,
    fallback_url: str | None = None,
) -> list[dict]:
    """Shape-check + sanitise each brief from the LLM.

    Drops malformed entries. Word-truncates over-long headlines /
    descriptions (rather than mid-word slicing). Validates landing_path
    against `allowed_urls` (the LINKS table from this week's facts plus
    the digest URL itself); a brief targeting an invented URL gets
    redirected to `fallback_url` rather than discarded — the keyword +
    copy work still has value, the operator can re-point if needed."""
    allowed_urls = allowed_urls or set()
    out: list[dict] = []
    for item in raw[:_MAX_BRIEFS]:
        if not isinstance(item, dict):
            continue
        theme = (item.get("theme") or "").strip()
        rationale = (item.get("rationale") or "").strip()
        landing_path = (item.get("landing_path") or "").strip()
        if not theme:
            continue
        # Validate landing — must be one of the URLs we offered.
        if not landing_path.startswith("/") or (
            allowed_urls and landing_path not in allowed_urls
        ):
            if fallback_url:
                landing_path = fallback_url
            else:
                continue

        keywords = [
            s.strip()[:_MAX_KEYWORD_CHARS]
            for s in (item.get("keywords") or [])
            if isinstance(s, str) and s.strip()
        ]
        ad_headlines = [
            t for t in (
                _word_truncate(s, _MAX_HEADLINE_CHARS)
                for s in (item.get("ad_headlines") or [])
                if isinstance(s, str)
            )
            if t
        ]
        ad_descriptions = [
            t for t in (
                _word_truncate(s, _MAX_DESCRIPTION_CHARS)
                for s in (item.get("ad_descriptions") or [])
                if isinstance(s, str)
            )
            if t
        ]
        if not (keywords and ad_headlines and ad_descriptions):
            continue
        out.append({
            "theme": theme[:60],
            "rationale": rationale[:300],
            "keywords": keywords,
            "ad_headlines": ad_headlines,
            "ad_descriptions": ad_descriptions,
            "landing_path": landing_path,
        })
    return out


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


# Minimum interval between generations. Lowered from 24h to 12h after
# the Sunday cron skipped a digest mid-RG because the previous run had
# fired ~20h earlier — during a Slam we want the morning recap before
# matches start regardless of whether the last digest is barely outside
# yesterday's window. 12h still rate-limits ad-hoc triggers (the admin
# endpoint can't be hammered into back-to-back generations) but doesn't
# block the daily morning slot when Slams are running.
_MIN_REGEN_INTERVAL = timedelta(hours=12)

# Default lookback when no previous digest exists. Roughly the "weekly"
# behaviour we want for the first-ever run.
_DEFAULT_LOOKBACK = timedelta(days=7)


class DigestResult:
    """Lightweight wrapper to communicate why generate_digest returned
    what it did. The caller (cron / CLI / admin endpoint) can branch on
    this to log appropriately or show a "wait N hours" message."""
    def __init__(
        self,
        row: EditorialDigest | None,
        *,
        status: str,
        message: str = "",
    ):
        self.row = row
        self.status = status  # 'created' | 'skipped_rate_limited' | 'skipped_no_facts' | 'failed'
        self.message = message

    def __bool__(self) -> bool:
        return self.row is not None


def generate_digest(
    session: Session,
    *,
    force: bool = False,
    editorial_notes: list[str] | None = None,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
    anchor_date: date | None = None,
) -> DigestResult:
    """Top-level entry: collect facts since the last digest, call Claude,
    persist a new row.

    Defaults — what the Monday cron + ad-hoc admin trigger both use:
      - `period_end` = now
      - `period_start` = last digest's period_end (or 7 days ago for the
        first-ever digest)
      - `anchor_date` = today (URL slug)

    Override `period_start` / `period_end` for backfill of historical
    weeks where you want a specific window. Use `editorial_notes` for
    verified human-supplied facts (milestones, retirements, etc.).

    Rate limit: refuses to generate when the last digest was published
    within `_MIN_REGEN_INTERVAL` (12h) — unless `force=True`. The
    caller decides whether to alert the user that they need to wait.
    """
    now = datetime.utcnow()
    last = session.exec(
        select(EditorialDigest).order_by(EditorialDigest.generated_at.desc()).limit(1)
    ).first()

    # 24h rate-limit gate. Force=True is the escape hatch for re-runs
    # of an already-published digest (prompt iteration, data fix, etc.).
    if last is not None and not force:
        age = now - last.generated_at
        if age < _MIN_REGEN_INTERVAL:
            hours = _MIN_REGEN_INTERVAL - age
            log.info(
                "digest rate-limit: last digest %s is %s old (< 12h), skipping",
                last.week_start, age,
            )
            return DigestResult(
                last,
                status="skipped_rate_limited",
                message=(
                    f"A digest was generated {age.total_seconds() // 3600:.0f}h ago. "
                    f"Try again in {hours.total_seconds() // 3600:.0f}h or pass force=True."
                ),
            )

    # Compute the coverage window. The natural sliding window: from
    # last digest's period_end to now.
    if period_end is None:
        period_end = now
    if period_start is None:
        if last is not None and last.period_end is not None:
            period_start = last.period_end
        elif last is not None:
            # Legacy row without period_end — use its anchor + 7 days.
            period_start = datetime.combine(last.week_start, time.min) + timedelta(days=7)
        else:
            period_start = period_end - _DEFAULT_LOOKBACK
    if anchor_date is None:
        anchor_date = period_end.date()

    # Anchor uniqueness check: if a digest already exists at this
    # date and not force, return it (handles same-day re-runs that
    # somehow slipped past the rate limit, e.g. an admin generation
    # at 00:01 UTC after a Mon cron at 06:00 UTC on a different day —
    # rare but cheap to defend against).
    same_anchor = session.exec(
        select(EditorialDigest).where(EditorialDigest.week_start == anchor_date)
    ).first()
    if same_anchor and not force:
        return DigestResult(
            same_anchor,
            status="skipped_rate_limited",
            message=f"A digest already exists for {anchor_date}; pass force=True to overwrite.",
        )

    facts = collect_period_facts(session, period_start, period_end)
    # Carry forward editorial_notes from the previous digest IF the
    # caller didn't supply any AND we're in the same coverage window
    # (caller is regenerating an existing recap with force=True).
    # Otherwise notes are one-time-per-recap context.
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
        log.info(
            "No newsworthy facts for window %s → %s — skipping",
            period_start, period_end,
        )
        return DigestResult(
            None, status="skipped_no_facts",
            message="No newsworthy facts in the window.",
        )

    result = _call_claude(facts)
    if result is None:
        return DigestResult(
            None, status="failed",
            message="LLM call failed or returned no usable response.",
        )
    headline, body, campaign_briefs, news_sources = result
    body = sanitize_body_links(body, facts.get("links", {}))
    briefs_blob = json.dumps(campaign_briefs) if campaign_briefs else None
    # Pack the LLM-self-reported source citations into source_json
    # alongside the input facts — readers see them in the digest UI,
    # and audits get the model's own view of which news it used.
    facts_with_sources = dict(facts)
    facts_with_sources["news_sources"] = news_sources

    if same_anchor and force:
        same_anchor.headline = headline
        same_anchor.body_md = body
        same_anchor.source_json = json.dumps(facts_with_sources)
        same_anchor.campaign_briefs_json = briefs_blob
        same_anchor.model_name = MODEL_NAME
        same_anchor.period_start = period_start
        same_anchor.period_end = period_end
        same_anchor.generated_at = now
        session.add(same_anchor)
        session.commit()
        session.refresh(same_anchor)
        return DigestResult(same_anchor, status="created")

    row = EditorialDigest(
        week_start=anchor_date,
        period_start=period_start,
        period_end=period_end,
        headline=headline,
        body_md=body,
        source_json=json.dumps(facts_with_sources),
        campaign_briefs_json=briefs_blob,
        model_name=MODEL_NAME,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return DigestResult(row, status="created")


# Backwards-compat shim: the backfill script + scheduler used to pass
# a week_start date. Translate to the new period-based API.
def generate_digest_for_week(
    session: Session,
    week_start: date,
    *,
    force: bool = False,
    editorial_notes: list[str] | None = None,
) -> EditorialDigest | None:
    """Generate (or return existing) a digest for a specific ISO week.
    Convenience wrapper used by the backfill script. New code should
    call `generate_digest()` directly without a week argument."""
    week_start = monday_of(week_start)
    period_start = datetime.combine(week_start, time.min)
    period_end = datetime.combine(week_start + timedelta(days=6), time.max)
    result = generate_digest(
        session,
        force=force,
        editorial_notes=editorial_notes,
        period_start=period_start,
        period_end=period_end,
        anchor_date=week_start,
    )
    return result.row
