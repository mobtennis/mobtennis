"""Render an editorial digest into a vertical (1080x1920) short-form MP4.

Local-tooling for the Reels/Shorts/TikTok workflow. Reads a digest
dict (headline + body_md as returned by /api/digests/{week}) and
produces a ~22-second silent MP4 with Ken-Burns-pan cards.

Each story card pulls a player image from `/api/players/{slug}` if
the sentence names a player whose slug appears in the digest's
internal markdown links. Cards without a usable player image fall
back to a text-only cream-and-green design.

Pillow renders each card as a 1080x1920 PNG; FFmpeg `zoompan` pans
each card into a short clip; FFmpeg `concat` stitches them.

No music, no voiceover yet — silent MP4. Add those in v2.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from slugify import slugify

API_BASE = "https://api.mob.tennis"
_IMG_CACHE_DIR = Path("/tmp/digest-video-cache")

# Frame is 1080x1920 (TikTok / Reels / Shorts native 9:16). 30fps gives
# smooth Ken-Burns without ballooning the file size.
W, H = 1080, 1920
FPS = 30

# Light-and-sunny palette per the visual-design memory: cream and
# grass-green, never a dark theme. Slightly cooler ink for readable
# body text on cream.
BG_CREAM = (250, 247, 240)
BG_GREEN = (47, 110, 75)
INK_DARK = (24, 34, 30)
INK_ON_GREEN = (245, 240, 225)
ACCENT = (191, 76, 41)  # warm coral for the brand line

# Mac system-font fallback chain. Headless Linux deployments would need
# their own font path; we'll cross that bridge if we ever render on the
# server (currently local-only per current scope).
_FONT_CANDIDATES_BOLD = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
_FONT_CANDIDATES_REGULAR = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    for c in (_FONT_CANDIDATES_BOLD if bold else _FONT_CANDIDATES_REGULAR):
        try:
            return ImageFont.truetype(c, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _strip_md_links(text: str) -> str:
    """Collapse `[anchor](url)` to just the anchor. The digest body
    carries both internal slug links and external news citations; for
    a video card we want the prose only."""
    return re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> list[str]:
    """Greedy word-wrap respecting glyph widths."""
    lines: list[str] = []
    cur: list[str] = []
    for word in text.split():
        trial = " ".join(cur + [word])
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] > max_w and cur:
            lines.append(" ".join(cur))
            cur = [word]
        else:
            cur.append(word)
    if cur:
        lines.append(" ".join(cur))
    return lines


@dataclass
class Card:
    body: str
    bg: tuple[int, int, int]
    text_color: tuple[int, int, int]
    font_size: int
    bold: bool
    eyebrow: str | None = None  # small uppercase label above the body
    image_path: Path | None = None  # full-bleed background image; text overlaid
    image_credit: str | None = None  # tiny credit line under brand


# Match `[Player Name](/players/some-slug)` — the digest body's internal
# player links. We use these to know which slugs to fetch images for,
# AND which name strings to look for in each card's text.
_PLAYER_LINK_RE = re.compile(r"\[([^\]]+)\]\(/players/([a-z0-9-]+)\)")

# Title-Case proper-noun spans of 2-3 words. Catches player names that
# the LLM mentioned but didn't link (the prompt heavily prioritises
# external news citations now, so internal /players/ links are
# often absent). Allows accented letters in lowercase tails.
_TITLE_CASE_NAME = re.compile(
    r"\b([A-Z][a-zà-ÿ]+(?:\s[A-Z][a-zà-ÿ]+){1,2})\b",
)

# Common Title-Case phrases that aren't player names — filtered so we
# don't waste API calls on every paragraph's "French Open" or
# "Grand Slam".
_NAME_BLOCKLIST = frozenset({
    "French Open", "Australian Open", "Us Open", "US Open",
    "Roland Garros", "Wimbledon Championships", "Grand Slam",
    "Open Era", "Indian Wells", "Monte Carlo", "Madrid Open",
    "Italian Open", "Canadian Open", "Cincinnati Open",
    "Shanghai Masters", "Paris Masters", "Miami Open",
    "Davis Cup", "Bjk Cup", "Bjkn Cup", "Court Philippe",
    "Court Suzanne", "Center Court", "Centre Court",
    "World No", "No.", "Sunday", "Monday", "Tuesday",
    "Wednesday", "Thursday", "Friday", "Saturday",
    "Defending Champion", "Ukrainian", "Russian",
})


@dataclass
class PlayerRef:
    slug: str
    display_name: str  # the anchor text — what the LLM chose to call them
    image_path: Path | None


def _fetch_player_images(body_md: str) -> list[PlayerRef]:
    """Return ordered, de-duped PlayerRefs for every player referenced
    in the body — explicit markdown links first, then Title-Case
    proper-noun discovery as a fallback. Images are downloaded to
    a local cache.
    """
    _IMG_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    refs: list[PlayerRef] = []

    # Pass 1: explicit `[Name](/players/slug)` links. Highest confidence.
    for m in _PLAYER_LINK_RE.finditer(body_md):
        anchor, slug = m.group(1), m.group(2)
        if slug in seen:
            continue
        seen.add(slug)
        refs.append(
            PlayerRef(slug=slug, display_name=anchor, image_path=_cached_image(slug)),
        )

    # Pass 2: Title-Case names → slug guess via python-slugify → try
    # /api/players/{slug}. Strip markdown first so anchor text inside
    # link syntax is matched once, not twice.
    plain = _strip_md_links(body_md)
    for m in _TITLE_CASE_NAME.finditer(plain):
        name = m.group(1)
        if name in _NAME_BLOCKLIST:
            continue
        slug = slugify(name)
        if slug in seen or not slug:
            continue
        # /api/players/{slug} 404s if the slug isn't real; _cached_image
        # returns None on 404 so we just skip it.
        img = _cached_image(slug)
        seen.add(slug)
        if img is not None:
            refs.append(PlayerRef(slug=slug, display_name=name, image_path=img))

    return refs


def _cached_image(slug: str) -> Path | None:
    """Fetch this player's image_url and cache locally. Returns the
    local path, or None if the player has no image."""
    # Cheap content-disposition handling: just use the slug as the
    # filename and let PIL detect the format on load.
    for ext in ("jpg", "jpeg", "png", "webp"):
        candidate = _IMG_CACHE_DIR / f"{slug}.{ext}"
        if candidate.exists():
            return candidate
    try:
        with urllib.request.urlopen(f"{API_BASE}/api/players/{slug}") as r:
            data = json.load(r)
    except Exception:
        return None
    url = data.get("image_url")
    if not url:
        return None
    # Guess the extension from the URL's tail; default to jpg.
    ext = "jpg"
    for cand in ("jpg", "jpeg", "png", "webp"):
        if url.lower().split("?")[0].endswith(f".{cand}"):
            ext = cand
            break
    out = _IMG_CACHE_DIR / f"{slug}.{ext}"
    try:
        urllib.request.urlretrieve(url, out)
    except Exception:
        return None
    # Verify Pillow can open it — guards against an HTML error page
    # masquerading as a JPG.
    try:
        with Image.open(out) as im:
            im.verify()
    except Exception:
        out.unlink(missing_ok=True)
        return None
    return out


def _pick_image_for_sentence(
    sentence: str, refs: list[PlayerRef],
) -> PlayerRef | None:
    """Return the first PlayerRef whose display name (or last name) is
    mentioned in `sentence` AND has an image we successfully cached.
    """
    for r in refs:
        if not r.image_path:
            continue
        # Try the full display name first; fall back to the surname so
        # "Gauff" matches "Coco Gauff" linked elsewhere in the body.
        if r.display_name in sentence:
            return r
        parts = r.display_name.split()
        if parts and parts[-1] in sentence:
            return r
    return None


def _cover_resize(im: Image.Image, w: int, h: int) -> Image.Image:
    """Resize+crop to fill (w, h) with the source's center retained
    (CSS `object-fit: cover` equivalent). Player photos vary wildly
    in aspect ratio — without center-crop, a portrait shot stretches
    horribly when slammed into 1080x1920."""
    sw, sh = im.size
    scale = max(w / sw, h / sh)
    nw, nh = int(sw * scale), int(sh * scale)
    im = im.resize((nw, nh), Image.LANCZOS)
    left = (nw - w) // 2
    top = (nh - h) // 2
    return im.crop((left, top, left + w, top + h))


def _render_card_png(card: Card, path: Path) -> None:
    if card.image_path is not None:
        _render_image_card(card, path)
    else:
        _render_text_card(card, path)


def _render_text_card(card: Card, path: Path) -> None:
    img = Image.new("RGB", (W, H), card.bg)
    draw = ImageDraw.Draw(img)

    # Centered body. Wrap to ~85% of frame width so text breathes.
    body_font = _font(card.font_size, bold=card.bold)
    lines = _wrap(draw, card.body, body_font, int(W * 0.85))
    line_h = card.font_size + 16
    total_h = len(lines) * line_h
    y = (H - total_h) // 2

    # Eyebrow label (small, uppercase) sits above the body block when
    # provided — used on the hook card to set up the recap.
    if card.eyebrow:
        eb_font = _font(36, bold=True)
        eb_bbox = draw.textbbox((0, 0), card.eyebrow, font=eb_font)
        eb_x = (W - (eb_bbox[2] - eb_bbox[0])) // 2
        eb_y = y - 90
        draw.text((eb_x, eb_y), card.eyebrow, font=eb_font, fill=ACCENT)

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=body_font)
        x = (W - (bbox[2] - bbox[0])) // 2
        draw.text((x, y), line, font=body_font, fill=card.text_color)
        y += line_h

    _draw_brand(draw, card.bg)
    img.save(path, "PNG")


def _render_image_card(card: Card, path: Path) -> None:
    """Full-bleed player image with a cream gradient overlay in the
    bottom 40% so the caption text remains legible regardless of the
    photo's underlying brightness."""
    assert card.image_path is not None
    with Image.open(card.image_path) as src:
        src = src.convert("RGB")
        bg = _cover_resize(src, W, H)

    # Gradient overlay: transparent at the top, full cream at the
    # bottom, sweeping across the lower 55% of the frame so the photo
    # still has presence but the caption block reads as a single
    # design surface.
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    grad_top = int(H * 0.45)
    for y in range(grad_top, H):
        # 0 → 255 alpha across the gradient strip.
        alpha = int(255 * (y - grad_top) / (H - grad_top))
        overlay_draw.rectangle(
            [(0, y), (W, y + 1)], fill=(*BG_CREAM, alpha),
        )
    composed = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(composed)
    body_font = _font(card.font_size, bold=card.bold)
    lines = _wrap(draw, card.body, body_font, int(W * 0.88))
    line_h = card.font_size + 18
    total_h = len(lines) * line_h
    # Anchor the text block in the lower third — centered vertically
    # in the cream-overlay region, with breathing room above the
    # brand mark.
    text_top = int(H * 0.66) - (total_h // 2)
    y = text_top
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=body_font)
        x = (W - (bbox[2] - bbox[0])) // 2
        draw.text((x, y), line, font=body_font, fill=card.text_color)
        y += line_h

    _draw_brand(draw, BG_CREAM)
    composed.save(path, "PNG")


def _draw_brand(draw: ImageDraw.ImageDraw, surface_bg: tuple[int, int, int]) -> None:
    """Bottom-margin wordmark, tinted for legibility on whatever the
    surface colour is."""
    brand_font = _font(42, bold=True)
    brand = "mob.tennis"
    bbox = draw.textbbox((0, 0), brand, font=brand_font)
    bx = (W - (bbox[2] - bbox[0])) // 2
    by = H - 110
    color = BG_GREEN if surface_bg == BG_CREAM else BG_CREAM
    draw.text((bx, by), brand, font=brand_font, fill=color)


# Sentence-split that keeps sentence-ending punctuation attached.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def cards_for_digest(digest: dict) -> list[Card]:
    """Build the slide list from a digest payload.

    Layout: hook (headline) → 3 substantive sentences from the body →
    outro. Story cards get a player photo when a referenced player
    has an image we can fetch; otherwise they fall back to a cream
    text-only card. Picks pictures BEFORE stripping the markdown so
    `/players/<slug>` references survive.
    """
    headline = digest["headline"].strip()
    body_raw = digest["body_md"]
    refs = _fetch_player_images(body_raw)
    body = _strip_md_links(body_raw).strip()
    sentences = _SENTENCE_SPLIT.split(body)
    chosen: list[str] = []
    for s in sentences:
        s = s.strip()
        if len(s) < 40:
            continue
        if s.lower().startswith(headline.lower()[:30]):
            continue
        chosen.append(s)
        if len(chosen) == 3:
            break

    cards: list[Card] = [
        Card(
            body=headline,
            bg=BG_CREAM,
            text_color=INK_DARK,
            font_size=88,
            bold=True,
            eyebrow="THIS WEEK IN TENNIS",
        ),
    ]
    used_slugs: set[str] = set()
    for s in chosen:
        # Don't reuse the same player photo twice — visual variety
        # matters more than picking the exact best match.
        candidate = _pick_image_for_sentence(s, [r for r in refs if r.slug not in used_slugs])
        if candidate:
            used_slugs.add(candidate.slug)
            cards.append(
                Card(
                    body=s,
                    bg=BG_CREAM,
                    text_color=INK_DARK,
                    font_size=52,
                    bold=True,
                    image_path=candidate.image_path,
                ),
            )
        else:
            cards.append(
                Card(
                    body=s,
                    bg=BG_CREAM,
                    text_color=INK_DARK,
                    font_size=58,
                    bold=False,
                ),
            )
    cards.append(
        Card(
            body="Read the recap\nmob.tennis",
            bg=BG_GREEN,
            text_color=INK_ON_GREEN,
            font_size=80,
            bold=True,
        ),
    )
    return cards


# Per-card hold time, seconds. Hook is short (hooks should hook fast),
# stories get reading time, outro is a beat.
_CARD_DURATIONS = (3.0, 5.5, 5.5, 5.5, 3.0)


def render_digest_video(digest: dict, output: Path) -> Path:
    """Render `digest` to a vertical MP4 at `output`. Returns the path."""
    cards = cards_for_digest(digest)
    # If the digest body had fewer than 3 substantive sentences (rare —
    # off-week recap), the duration tuple is longer than the card list.
    # Truncate to whichever is shorter so we don't index past the end.
    durations = list(_CARD_DURATIONS)[: len(cards)]
    while len(durations) < len(cards):
        durations.append(5.0)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)

        # 1. Render each card to PNG.
        pngs: list[Path] = []
        for i, c in enumerate(cards):
            p = tmp_dir / f"card_{i:02d}.png"
            _render_card_png(c, p)
            pngs.append(p)

        # 2. Per-card clip with a subtle Ken-Burns zoom-in. Pure still
        #    frames feel dead in vertical short form; a slow 1.00→1.06
        #    zoom adds motion without distracting from the text.
        clips: list[Path] = []
        for i, (png, dur) in enumerate(zip(pngs, durations)):
            clip = tmp_dir / f"clip_{i:02d}.mp4"
            frames = int(dur * FPS)
            # zoompan zoom-rate: target 6% growth across the clip.
            zoom_step = 0.06 / frames
            subprocess.run(
                [
                    "ffmpeg", "-loglevel", "error", "-y",
                    "-loop", "1", "-i", str(png),
                    "-vf", (
                        f"zoompan="
                        f"z='min(zoom+{zoom_step:.6f},1.06)':"
                        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                        f"d={frames}:s={W}x{H}:fps={FPS}"
                    ),
                    "-c:v", "libx264",
                    "-t", str(dur),
                    "-pix_fmt", "yuv420p",
                    "-r", str(FPS),
                    str(clip),
                ],
                check=True,
            )
            clips.append(clip)

        # 3. Concat. Re-encode rather than `-c copy` so the
        #    concat-demuxer is happy with any minor timestamp drift
        #    between the source clips.
        concat = tmp_dir / "concat.txt"
        concat.write_text(
            "\n".join(f"file '{c.absolute()}'" for c in clips) + "\n",
        )
        subprocess.run(
            [
                "ffmpeg", "-loglevel", "error", "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(concat),
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-r", str(FPS),
                str(output),
            ],
            check=True,
        )
    return output
