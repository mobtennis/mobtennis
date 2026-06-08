"""Bundle PlayerImages into Name the Pro sets.

Stratification per set (5 images):
  1×  rank   1-10   (one familiar headliner)
  2×  rank  11-50   (working tour pros)
  1×  rank  51-150  (challenger-edge)
  1×  rank 151-300  (deep tour)

Distractor logic per image (3 wrong options):
  1.  same-rank-band   — within ±20 ranks of the correct player
  2.  same-tour-other  — any other ranked player on the same tour
  3.  well-known foil  — top-30 on the same tour

NEVER cross tours — ATP images get ATP distractors only, WTA images
get WTA distractors only. (ITF tournaments use the same `tour` enum
in our Player table because the tour is keyed by gender, not by
the ATP/WTA sanctioning body, so ITF women appear in the WTA pool
naturally.)

Bundler is idempotent. Each PlayerImage used in a NameTheProImage
is excluded from future bundles. Same player can appear across
different sets via different photos — we only dedupe at the
photo level.
"""

from __future__ import annotations

import json
import logging
import random
from collections import defaultdict
from datetime import date, timedelta

from sqlmodel import Session, select

from app.models.name_the_pro import NameTheProImage, NameTheProSet
from app.models.player import Player
from app.models.player_image import PlayerImage

log = logging.getLogger(__name__)

IMAGES_PER_SET = 5

# Tier ranges (inclusive). Mix shapes the round so each set has
# one familiar headliner + four discovery rows. We treat ranks
# 51-300 as one "deep" bucket because the face-detection pool
# below rank 150 is currently thin — collapsing the two avoids
# the bundler stalling out when one sub-bucket is empty.
TIERS = {
    "top10": (1, 10),
    "high_mid": (11, 50),
    "deep": (51, 300),
}
TIER_QUOTAS = {"top10": 1, "high_mid": 2, "deep": 2}


def _next_publish_date(session: Session) -> date:
    last = session.exec(
        select(NameTheProSet.publish_date)
        .order_by(NameTheProSet.publish_date.desc())
        .limit(1)
    ).first()
    today = date.today()
    if not last:
        return today
    return max(last + timedelta(days=1), today)


def _tier_of(rank: int | None) -> str | None:
    if rank is None:
        return None
    for name, (lo, hi) in TIERS.items():
        if lo <= rank <= hi:
            return name
    return None


def _commons_file_page_url(upload_url: str) -> str | None:
    import re
    from urllib.parse import quote
    m = re.match(
        r"https://upload\.wikimedia\.org/wikipedia/commons/(?:thumb/)?[0-9a-f]/[0-9a-f]{2}/([^/?#]+)",
        upload_url,
    )
    if not m:
        return None
    return f"https://commons.wikimedia.org/wiki/File:{quote(m.group(1))}"


def _pick_distractors(
    session: Session,
    correct: Player,
    rng: random.Random,
) -> list[Player]:
    """Three distractors per the recipe:
    [same-band, same-tour-other, top-30-foil]. Falls back gracefully
    if any pool is thin — final list always has 3 unique players
    from the same tour as `correct`."""
    used: set[int] = {correct.id}
    out: list[Player] = []
    rank = correct.current_rank or 999

    def _pick_from(query) -> Player | None:
        candidates = [p for p in session.exec(query).all() if p.id not in used]
        if not candidates:
            return None
        choice = rng.choice(candidates)
        used.add(choice.id)
        return choice

    # 1. same-rank-band (±20)
    band_lo = max(1, rank - 20)
    band_hi = rank + 20
    band_q = (
        select(Player).where(
            Player.tour == correct.tour,
            Player.current_rank.is_not(None),
            Player.current_rank >= band_lo,
            Player.current_rank <= band_hi,
        )
    )
    if (p := _pick_from(band_q)) is not None:
        out.append(p)

    # 2. same-tour, anywhere on the ladder
    other_q = (
        select(Player).where(
            Player.tour == correct.tour,
            Player.current_rank.is_not(None),
        )
    )
    if (p := _pick_from(other_q)) is not None:
        out.append(p)

    # 3. top-30 foil
    foil_q = (
        select(Player).where(
            Player.tour == correct.tour,
            Player.current_rank.is_not(None),
            Player.current_rank <= 30,
        )
    )
    if (p := _pick_from(foil_q)) is not None:
        out.append(p)

    # Backfill from any same-tour player if any of the 3 strategies
    # came up empty (small tour, sparse data, etc.). Better to have
    # 3 distractors than abort the whole set.
    while len(out) < 3:
        any_q = select(Player).where(
            Player.tour == correct.tour,
            Player.id.notin_(used),
            Player.current_rank.is_not(None),
        )
        backfill = session.exec(any_q).all()
        if not backfill:
            break
        p = rng.choice(backfill)
        used.add(p.id)
        out.append(p)
    return out


def _eligible_pool(
    session: Session, used_image_ids: set[int],
) -> dict[str, list[tuple[PlayerImage, Player]]]:
    """Hero-eligible PlayerImages joined to their Player, grouped
    by ranking tier. Excludes images already used in NTP sets and
    images that haven't passed the face-visibility check."""
    rows = session.exec(
        select(PlayerImage, Player)
        .join(Player, Player.id == PlayerImage.player_id)
        .where(
            # Deliberately NOT filtering on is_hero_eligible: that
            # flag picks landscape action shots for the player-page
            # hero band. NTP wants the opposite — a clean portrait
            # where the face is obviously the subject. Most rows
            # are not hero_eligible, so requiring it leaves the
            # picker with almost nothing to draw from.
            PlayerImage.is_hidden == False,        # noqa: E712
            # NTP-specific: only photos where YuNet found a face of
            # usable size. Photos with face_detected==None (not yet
            # scanned) or False (no face) are deferred — the scanner
            # script can clear the backlog and a re-bundle picks them
            # up automatically.
            PlayerImage.face_detected == True,     # noqa: E712
            Player.current_rank.is_not(None),
            Player.current_rank <= 300,
        )
    ).all()
    grouped: dict[str, list[tuple[PlayerImage, Player]]] = defaultdict(list)
    for img, player in rows:
        if img.id in used_image_ids:
            continue
        tier = _tier_of(player.current_rank)
        if tier:
            grouped[tier].append((img, player))
    return grouped


def bundle_ntp(
    session: Session, rng: random.Random | None = None,
) -> list[NameTheProSet]:
    """Form as many sets-of-5 as the eligible pool allows. Each
    set has the tier quota above and 3 distractors per image.
    """
    if rng is None:
        rng = random.Random()

    used_ids = set(session.exec(
        select(NameTheProImage.source_player_image_id).where(
            NameTheProImage.source_player_image_id.is_not(None),
        )
    ).all())

    grouped = _eligible_pool(session, used_ids)
    sets_built: list[NameTheProSet] = []

    while all(len(grouped.get(t, [])) >= TIER_QUOTAS[t] for t in TIER_QUOTAS):
        # Pick the set's 5 images respecting the tier quota AND no
        # duplicate-player rule.
        picks: list[tuple[PlayerImage, Player]] = []
        used_players: set[int] = set()
        ok = True
        for tier, quota in TIER_QUOTAS.items():
            avail = [
                ip for ip in grouped[tier] if ip[1].id not in used_players
            ]
            if len(avail) < quota:
                ok = False
                break
            chosen = rng.sample(avail, quota)
            picks.extend(chosen)
            for _, player in chosen:
                used_players.add(player.id)
        if not ok:
            break

        # Build the set + per-image rows.
        new_set = NameTheProSet(
            publish_date=_next_publish_date(session),
            is_published=True,
        )
        session.add(new_set)
        session.flush()
        new_set.title = f"Round {new_set.id}"

        for position, (img, player) in enumerate(picks, start=1):
            distractors = _pick_distractors(session, player, rng)
            # 4 options total, shuffled per row so the correct slot
            # isn't always at the same index.
            options = [
                {"slug": player.slug, "full_name": player.full_name or player.slug},
                *[{"slug": d.slug, "full_name": d.full_name or d.slug} for d in distractors],
            ]
            rng.shuffle(options)

            ntp_img = NameTheProImage(
                set_id=new_set.id,
                position=position,
                image_url=img.url,
                caption=player.full_name or player.slug,
                options_json=json.dumps(options),
                correct_player_slug=player.slug,
                source_player_image_id=img.id,
                source_url=_commons_file_page_url(img.url),
                credit=img.credit,
                license_url=img.license_url,
            )
            session.add(ntp_img)
            # Remove the picked photo from the pool so the next set
            # doesn't include it again.
            grouped[_tier_of(player.current_rank) or "low"].remove((img, player))

        session.commit()
        sets_built.append(new_set)
        log.info(
            "ntp: bundled set %d (publish_date=%s) with %d images",
            new_set.id, new_set.publish_date, len(picks),
        )

    return sets_built
