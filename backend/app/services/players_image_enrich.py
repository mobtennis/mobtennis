"""Collect Wikipedia / Wikimedia Commons photos for each player.

For each player we try to populate `player_images` from three
sources, in order of priority:

  1. Wikipedia infobox lead image (the canonical "headshot" photo)
  2. Every image embedded on the player's Wikipedia article body
  3. The corresponding Commons category, if one exists (often the
     gold mine — "Category:Aryna Sabalenka" has dozens of tournament
     shots not all linked from the main article)

Each discovered image becomes a PlayerImage row, deduped on URL.
Re-runs of the enricher merge new images without disturbing
admin-set primary/hidden flags. Wikipedia infobox image is what we
mark as `is_primary=True` on first run; admins can flip the primary
later via the admin endpoint.

Player.image_url is kept synchronised to the primary's URL so all
existing call sites (PlayerAvatar, MatchCard, RankingsRow) keep
working unchanged.

License compliance:
  - Each image carries its photographer credit + license URL.
  - We filter out non-free / fair-use rationale images (those exist
    on Wikipedia legally only because Wikipedia itself is providing
    encyclopedic commentary; we have no such defence).
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime
from urllib.parse import unquote

import httpx
from sqlmodel import Session, select

from app.models.player import Player
from app.models.player_image import PlayerImage

log = logging.getLogger(__name__)

UA = "Tennismob/0.1 (https://mob.tennis; bot@mob.tennis)"
MEDIAWIKI_API = "https://en.wikipedia.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"

# Wikipedia's public API throttles aggressively when a single client
# fires many requests in a tight loop. The enricher can spawn 30+
# imageinfo calls per player (article + commons category files); the
# per-player CLI sleep alone isn't enough. We add a small inter-call
# delay AND a 429-aware retry that respects Retry-After.
_MIN_CALL_INTERVAL = 0.12  # seconds between consecutive Wikipedia calls
_last_call_at = 0.0


def _polite_get(
    client: httpx.Client, url: str, *, params: dict | None = None, max_retries: int = 4,
) -> httpx.Response | None:
    """GET with throttle + retry-on-429. Returns None when retries
    exhaust (the caller treats that as a soft failure)."""
    global _last_call_at
    for attempt in range(max_retries + 1):
        elapsed = time.monotonic() - _last_call_at
        if elapsed < _MIN_CALL_INTERVAL:
            time.sleep(_MIN_CALL_INTERVAL - elapsed)
        _last_call_at = time.monotonic()
        try:
            r = client.get(url, params=params)
        except httpx.HTTPError as e:
            log.warning("Wikipedia GET failed (%s): %s", url, e)
            return None
        if r.status_code != 429:
            return r
        # Throttle hit. Honour Retry-After if present; otherwise
        # exponential backoff starting at 2 seconds.
        retry_after = r.headers.get("Retry-After")
        try:
            wait = float(retry_after) if retry_after else 2 ** (attempt + 1)
        except ValueError:
            wait = 2 ** (attempt + 1)
        log.info(
            "Wikipedia 429 — backing off %.1fs (attempt %d/%d)",
            wait, attempt + 1, max_retries,
        )
        time.sleep(min(wait, 30.0))
    return None

_HTML_TAG_RE = re.compile(r"<[^>]+>")

_LICENSE_DENY_SUBSTRINGS = (
    "FAIR-USE", "FAIR-USE-RATIONALE", "NON-FREE", "ALL-RIGHTS-RESERVED",
    "COPYRIGHTED",
)
_LICENSE_ALLOW_SUBSTRINGS = (
    "CC-BY", "CC0", "PUBLIC-DOMAIN", "GFDL", "PD-", "PD,",
)

# We only want photos. Wikipedia articles also embed signatures,
# trophies, flags, stadium diagrams, etc. — heuristic filename
# filters skip the obvious non-portraits.
_FILENAME_DENY = (
    "signature", "logo", "flag_of_", "coat_of_arms",
    ".svg", ".gif",
    # Audio / video / docs — turn up in Commons search hits even when
    # filtered to namespace 6 (e.g. pronunciation .wav files filed
    # under a player's name). Image-only file types pass through.
    ".wav", ".ogg", ".oga", ".mp3", ".webm", ".mp4", ".mov", ".pdf",
)

# Filename markers that signal an image is a tight portrait crop, not
# a landscape action shot. Used by the hero-eligibility heuristic so
# the profile-page header band doesn't get filled with a center-
# cropped chest/armpit area.
_HERO_FILENAME_DENY = (
    "(cropped)", "cropped)", "_cropped", "-cropped",
    "portrait", "headshot", "face",
)


def _strip_html(s: str | None) -> str | None:
    if not s:
        return None
    return re.sub(r"\s+", " ", _HTML_TAG_RE.sub("", s)).strip() or None


def _normalize_license(short: str | None) -> str | None:
    if not short:
        return None
    return re.sub(r"[\s_]+", "-", short.strip()).upper()


def _license_allowed(normalised: str | None) -> bool:
    if not normalised:
        return False
    if any(d in normalised for d in _LICENSE_DENY_SUBSTRINGS):
        return False
    if normalised == "PD":
        return True
    return any(a in normalised for a in _LICENSE_ALLOW_SUBSTRINGS)


def _filename_allowed(filename: str) -> bool:
    lower = filename.lower()
    return not any(b in lower for b in _FILENAME_DENY)


def _is_hero_eligible(
    filename: str, width: int | None, height: int | None,
) -> bool:
    """Heuristic: which images make a decent landscape header band?

    Wants landscape aspect (width > height), enough resolution to fill
    a desktop 1080px+ width band without pixelation, and a filename
    that doesn't signal a tight crop.

    Returns False on portraits, low-res images, and Wikipedia
    "(cropped)" / "portrait" / "headshot" variants.
    """
    if not width or not height:
        return False
    if width < 1000:
        return False
    # Landscape: ratio of long edge to short edge between 1.2 and 2.5.
    # Pure squares look squished in the band; ultrawides waste space
    # cropping the player out.
    ratio = width / height
    if ratio < 1.2 or ratio > 2.5:
        return False
    lower = filename.lower()
    return not any(b in lower for b in _HERO_FILENAME_DENY)


def _title_from_wikipedia_url(url: str) -> str | None:
    m = re.match(r"https?://en\.wikipedia\.org/wiki/(.+)$", url)
    if not m:
        return None
    return unquote(m.group(1)).replace("_", " ")


# --------------------------- API wrappers ----------------------------


def _discover_wikipedia_url(
    client: httpx.Client, full_name: str,
) -> str | None:
    """Best-effort: turn a player's full name into a Wikipedia URL.

    Most retired legends (Nadal, Court, Evert) lack a wikipedia_url
    in our DB because the Wikidata pipeline only ran for currently-
    ranked players. Their Wikipedia articles almost always sit at the
    obvious slug; we verify the page is about a tennis player before
    accepting (extract must contain 'tennis').
    """
    if not full_name:
        return None
    title = full_name.strip().replace(" ", "_")
    r = _polite_get(
        client, f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}",
    )
    if r is None or r.status_code != 200:
        return None
    data = r.json()
    if data.get("type") == "disambiguation":
        return None
    extract = (data.get("extract") or "").lower()
    if "tennis" not in extract:
        return None
    canonical = (data.get("content_urls") or {}).get("desktop", {}).get("page")
    if canonical:
        return canonical
    canonical_title = (data.get("titles") or {}).get("canonical")
    if canonical_title:
        return f"https://en.wikipedia.org/wiki/{canonical_title}"
    return None


def _get_lead_image_filename(client: httpx.Client, title: str) -> str | None:
    r = _polite_get(
        client, MEDIAWIKI_API,
        params={
            "action": "query", "titles": title, "prop": "pageimages",
            "piprop": "name", "format": "json", "redirects": "1",
        },
    )
    if r is None or r.status_code != 200:
        return None
    pages = r.json().get("query", {}).get("pages", {})
    if not pages:
        return None
    return next(iter(pages.values())).get("pageimage")


def _get_article_image_filenames(
    client: httpx.Client, title: str,
) -> list[str]:
    """Every image embedded on the article body. Used to surface action
    shots that aren't the infobox lead."""
    r = _polite_get(
        client, MEDIAWIKI_API,
        params={
            "action": "query", "titles": title, "prop": "images",
            "imlimit": "50", "format": "json", "redirects": "1",
        },
    )
    if r is None or r.status_code != 200:
        return []
    pages = r.json().get("query", {}).get("pages", {})
    if not pages:
        return []
    page = next(iter(pages.values()))
    images = page.get("images") or []
    # The "title" field is "File:Foo.jpg" — strip the prefix.
    out: list[str] = []
    for img in images:
        t = img.get("title", "")
        if t.startswith("File:"):
            out.append(t[5:])
    return out


def _search_commons_by_player_name(
    client: httpx.Client, player_name: str, limit: int = 100,
) -> list[str]:
    """Files on Commons whose title contains the player's name.

    The category-driven discovery in `_get_commons_category_files`
    only finds images filed under `Category:<Player Name>`. Lots of
    great action shots from official tournament photographers don't
    end up in the per-player category — they live in
    `Category:2025 Wimbledon Championships` etc., and the only way
    we'd discover them through the existing crawl is to walk every
    tournament-edition category (slow + noisy).

    This full-text search uses `intitle:"<name>"` to require the
    player's name in the FILE TITLE — typical pattern is
    "2024 Roland Garros — Carlos Alcaraz forehand.jpg" — which is a
    strong signal that the file is actually of that player. False
    positives are mitigated downstream by the size, license, and
    hero-eligibility filters; the worst-case is an operator skip.

    Returns up to `limit` filenames (without "File:" prefix).
    """
    r = _polite_get(
        client, COMMONS_API,
        params={
            "action": "query", "list": "search",
            # intitle: requires the phrase in the title, exact-match
            # quoting handles two-word names like "Iga Świątek".
            "srsearch": f'intitle:"{player_name}"',
            # File namespace only — skip article descriptions.
            "srnamespace": "6",
            "srlimit": str(limit),
            "format": "json",
        },
    )
    if r is None or r.status_code != 200:
        return []
    hits = r.json().get("query", {}).get("search", []) or []
    out: list[str] = []
    for h in hits:
        t = h.get("title", "")
        if t.startswith("File:"):
            out.append(t[5:])
    return out


def _get_commons_category_files(
    client: httpx.Client, category_title: str,
) -> list[str]:
    """Files in a Commons category, e.g. 'Aryna Sabalenka'. Most
    notable players have one; the category page lives at
    https://commons.wikimedia.org/wiki/Category:<Name>."""
    r = _polite_get(
        client, COMMONS_API,
        params={
            "action": "query", "list": "categorymembers",
            "cmtitle": f"Category:{category_title}",
            "cmtype": "file", "cmlimit": "50",
            "format": "json",
        },
    )
    if r is None or r.status_code != 200:
        return []
    members = r.json().get("query", {}).get("categorymembers", []) or []
    out: list[str] = []
    for m in members:
        t = m.get("title", "")
        if t.startswith("File:"):
            out.append(t[5:])
    return out


def _get_image_info(
    client: httpx.Client, filename: str,
) -> dict | None:
    """Return url + width + height + artist + license_short + license_url
    or None if the file can't be queried or its license isn't allowed."""
    r = _polite_get(
        client, MEDIAWIKI_API,
        params={
            "action": "query", "titles": f"File:{filename}",
            "prop": "imageinfo",
            "iiprop": "url|size|extmetadata", "format": "json",
        },
    )
    if r is None or r.status_code != 200:
        return None
    pages = r.json().get("query", {}).get("pages", {})
    if not pages:
        return None
    page = next(iter(pages.values()))
    infos = page.get("imageinfo") or []
    if not infos:
        return None
    info = infos[0]
    md = info.get("extmetadata") or {}

    def _md(key: str) -> str | None:
        v = md.get(key)
        return v.get("value") if isinstance(v, dict) else None

    license_short = _md("LicenseShortName")
    normalised = _normalize_license(license_short)
    if not _license_allowed(normalised):
        return None

    artist = _strip_html(_md("Artist") or _md("Credit"))
    credit_parts: list[str] = []
    if artist:
        credit_parts.append(artist)
    if license_short:
        credit_parts.append(license_short.strip())

    return {
        "url": info.get("url"),
        "width": info.get("width"),
        "height": info.get("height"),
        "artist": artist,
        "license_short": license_short,
        "license_url": _md("LicenseUrl"),
        "credit": " · ".join(credit_parts) or None,
    }


# --------------------------- Orchestration ---------------------------


def _commons_category_from_wikipedia_url(url: str) -> str:
    """Wikipedia article slug ≈ Commons category title in 99% of cases.

    Underscores → spaces for the API. Disambiguation suffixes like
    "_(tennis)" are kept since some categories include them ("Andy
    Murray (tennis)" doesn't exist as a category but "Andy Murray" does;
    we'll just fail gracefully on those).
    """
    title = _title_from_wikipedia_url(url) or ""
    return title


def _upsert_image(
    session: Session,
    player: Player,
    *,
    url: str,
    source: str,
    source_url: str | None,
    credit: str | None,
    license_url: str | None,
    width: int | None,
    height: int | None,
    filename: str,
    make_primary: bool,
) -> tuple[PlayerImage, bool]:
    """Insert a new PlayerImage row or refresh an existing one.

    Existing-row updates touch metadata (credit, license URL,
    dimensions, hero-eligibility) — they NEVER toggle is_primary,
    is_hero, or is_hidden, which are admin-controlled and sticky
    across re-runs.
    """
    hero_eligible = _is_hero_eligible(filename, width, height)
    existing = session.exec(
        select(PlayerImage).where(PlayerImage.url == url)
    ).first()
    if existing:
        existing.credit = credit or existing.credit
        existing.license_url = license_url or existing.license_url
        existing.width = width or existing.width
        existing.height = height or existing.height
        # Recompute hero-eligibility — heuristic may have improved
        # between runs (we added the filter, etc.).
        existing.is_hero_eligible = hero_eligible
        existing.updated_at = datetime.utcnow()
        session.add(existing)
        return existing, False

    img = PlayerImage(
        player_id=player.id,
        url=url,
        source=source,
        source_url=source_url,
        credit=credit,
        license_url=license_url,
        width=width,
        height=height,
        is_primary=make_primary,
        is_hero_eligible=hero_eligible,
    )
    session.add(img)
    session.flush()  # surface .id for the caller
    return img, True


def _sync_primary_pointer(session: Session, player: Player) -> None:
    """Player.image_url + Player.hero_image_url mirror whichever
    PlayerImage rows currently hold the is_primary and is_hero
    flags. Called after any enrichment write or admin flag change.
    """
    all_images = session.exec(
        select(PlayerImage).where(PlayerImage.player_id == player.id)
    ).all()

    # ----- Primary (headshot for avatars/match cards) -----
    primary = next(
        (i for i in all_images if i.is_primary and not i.is_hidden), None,
    )
    if not primary:
        order = {"wikipedia": 0, "commons": 1, "api-tennis": 2, "manual": 3}
        non_hidden = [i for i in all_images if not i.is_hidden]
        if non_hidden:
            primary = min(
                non_hidden, key=lambda i: (order.get(i.source, 99), i.id),
            )
            primary.is_primary = True
            session.add(primary)

    if primary and player.image_url != primary.url:
        player.image_url = primary.url
        player.image_source = primary.source
        player.image_credit = primary.credit
        player.image_license_url = primary.license_url
        player.updated_at = datetime.utcnow()
        session.add(player)

    # ----- Hero (landscape action shot for the profile-page band) -----
    # Admin-pinned hero wins; otherwise auto-pick the largest
    # eligible image (biggest pixel area = sharpest at hero size).
    # If nothing qualifies, hero_image_url stays null and the
    # frontend falls back to the primary with bg-top cropping.
    hero = next(
        (i for i in all_images if i.is_hero and not i.is_hidden), None,
    )
    if not hero:
        candidates = [
            i for i in all_images
            if i.is_hero_eligible and not i.is_hidden
        ]
        if candidates:
            hero = max(
                candidates,
                key=lambda i: ((i.width or 0) * (i.height or 0), i.id),
            )
            hero.is_hero = True
            session.add(hero)

    new_hero_url = hero.url if hero else None
    if player.hero_image_url != new_hero_url:
        player.hero_image_url = new_hero_url
        player.updated_at = datetime.utcnow()
        session.add(player)


def enrich_one(session: Session, player: Player, client: httpx.Client) -> int:
    """Discover all available images for `player`. Returns the count
    of newly-inserted PlayerImage rows (0 if nothing new)."""
    # Self-heal: discover wikipedia_url from name if missing.
    if not player.wikipedia_url and player.full_name:
        try:
            discovered = _discover_wikipedia_url(client, player.full_name)
        except Exception:
            discovered = None
        if discovered:
            player.wikipedia_url = discovered
            session.add(player)
            log.info("discovered wikipedia_url for %s: %s", player.slug, discovered)

    if not player.wikipedia_url:
        return 0
    title = _title_from_wikipedia_url(player.wikipedia_url)
    if not title:
        return 0

    new_count = 0
    seen_filenames: set[str] = set()

    # 1. Lead infobox image (priority for is_primary on first run).
    try:
        lead = _get_lead_image_filename(client, title)
    except httpx.HTTPError as e:
        log.warning("pageimages failed for %s: %s", player.slug, e)
        lead = None

    # Whether THIS player has any existing primary already. First-run
    # populations set the infobox lead as primary; re-runs do not.
    already_has_primary = bool(
        session.exec(
            select(PlayerImage).where(
                PlayerImage.player_id == player.id,
                PlayerImage.is_primary == True,  # noqa: E712
            )
        ).first()
    )

    def _add_filename(
        filename: str, source: str, *, primary_candidate: bool = False,
    ) -> None:
        nonlocal new_count
        if filename in seen_filenames or not _filename_allowed(filename):
            return
        seen_filenames.add(filename)
        try:
            info = _get_image_info(client, filename)
        except httpx.HTTPError:
            return
        if not info or not info.get("url"):
            return
        make_primary = (
            primary_candidate and not already_has_primary
        )
        _, inserted = _upsert_image(
            session, player,
            url=info["url"],
            source=source,
            source_url=player.wikipedia_url,
            credit=info["credit"],
            license_url=info["license_url"],
            width=info["width"],
            height=info["height"],
            filename=filename,
            make_primary=make_primary,
        )
        if inserted:
            new_count += 1

    if lead:
        _add_filename(lead, "wikipedia", primary_candidate=True)

    # 2. Other article-body images. Lots of these on top players —
    # action shots from trophy ceremonies, doubles partner photos, etc.
    try:
        article_files = _get_article_image_filenames(client, title)
    except httpx.HTTPError:
        article_files = []
    for fn in article_files:
        if fn == lead:
            continue
        _add_filename(fn, "wikipedia")

    # 3. Commons category (often the richest source — dedicated
    # tournament photographers upload entire match galleries here).
    cat_title = _commons_category_from_wikipedia_url(player.wikipedia_url)
    if cat_title:
        try:
            commons_files = _get_commons_category_files(client, cat_title)
        except httpx.HTTPError:
            commons_files = []
        for fn in commons_files:
            _add_filename(fn, "commons")

    # 4. Commons full-text search by player name. Picks up tournament-
    # edition category files like "2025 Roland Garros - Carlos Alcaraz
    # forehand.jpg" that aren't filed under the per-player category.
    # Largest yield of action shots for upper-tier players; for deep
    # tour names it returns 0-5 hits which is fine — the existing
    # sources already cover them.
    if player.full_name:
        try:
            search_files = _search_commons_by_player_name(
                client, player.full_name,
            )
        except httpx.HTTPError:
            search_files = []
        for fn in search_files:
            _add_filename(fn, "commons")

    _sync_primary_pointer(session, player)
    return new_count


def build_client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": UA}, timeout=15.0, follow_redirects=True,
    )
