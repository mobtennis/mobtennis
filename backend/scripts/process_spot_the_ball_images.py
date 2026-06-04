"""Inpaint the tennis ball out of each Spot the Ball photo.

Reads each calibrated puzzle from the prod API, downloads the source
image, paints over the ball area with a median-sampled background
color, blurs the edges so the patch blends, saves the edited file
to web/public/spot-the-ball/{date}.jpg, and updates the prod DB
row to point at the new URL.

Run AFTER calibration:

    python -m scripts.process_spot_the_ball_images

Re-runnable: each run reprocesses all calibrated puzzles. Cheap
enough to just iterate (one-time op on small datasets).

Requires Pillow locally + SSH access to prod for the DB update.
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import math
import shlex
import subprocess
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("process_stb")

API_BASE = "https://api.mob.tennis"
REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "web" / "public" / "spot-the-ball"

# Original Wikimedia URLs by puzzle_date. We overwrote image_url with
# the local path on first-pass processing, so this map lets a re-run
# pull the pristine source instead of the already-edited copy.
#
# Long-term fix would be a separate `original_image_url` column on the
# row, but a hardcoded map here is fine for the seeded set — when we
# add new puzzles via the seed script, append to this dict at the
# same time.
SOURCE_URLS: dict[str, str] = {
    "2026-06-04": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Rich%C3%A8l_Hogenkamp_-_Masters_de_Madrid_2015_-_11.jpg/960px-Rich%C3%A8l_Hogenkamp_-_Masters_de_Madrid_2015_-_11.jpg",
    "2026-06-03": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b6/2017_US_Open_Tennis_-_Qualifying_Rounds_-_Viktoriya_Tomova_%28BUL%29_def._Polona_Hercog_%28SLO%29_%2836916572131%29.jpg/960px-2017_US_Open_Tennis_-_Qualifying_Rounds_-_Viktoriya_Tomova_%28BUL%29_def._Polona_Hercog_%28SLO%29_%2836916572131%29.jpg",
    "2026-06-02": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/16/Kei_Nishikori_1%2C_Wimbledon_2013_-_Diliff.jpg/960px-Kei_Nishikori_1%2C_Wimbledon_2013_-_Diliff.jpg",
    "2026-06-01": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/10/Ana_Ivanovi%C4%87_-_Masters_de_Madrid_2015_-_01.jpg/960px-Ana_Ivanovi%C4%87_-_Masters_de_Madrid_2015_-_01.jpg",
    "2026-05-31": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6b/Javier_Mart%C3%AD_-_Masters_de_Madrid_2015_-_12.jpg/960px-Javier_Mart%C3%AD_-_Masters_de_Madrid_2015_-_12.jpg",
    "2026-05-30": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b3/Andreea_Mitu_-_Masters_de_Madrid_2015_-_05.jpg/960px-Andreea_Mitu_-_Masters_de_Madrid_2015_-_05.jpg",
}

# Ball-area radius in pixels at the canonical 960px image width.
# Scaled per-image to the actual width. Tennis balls in close shots
# typically span ~15-25px; we over-paint to ~30px to leave no halo.
BALL_RADIUS_AT_960 = 32

# Annulus from which we sample background colors. Outer ring (3x
# the ball radius) captures clean background; inner ring (1.5x)
# skips the ball + immediate shadow.
SAMPLE_INNER_FACTOR = 1.5
SAMPLE_OUTER_FACTOR = 3.0

# Feather radius — Gaussian blur applied to the patched circle so
# the painted disc bleeds into the surrounding background without
# a hard edge.
FEATHER_RADIUS = 8


def _download(url: str, max_retries: int = 5) -> Image.Image:
    """Polite GET that honours 429 + Retry-After. Wikimedia's
    upload.wikimedia.org will rate-limit consecutive same-host
    requests hard."""
    import time
    log.info("  downloading %s", url[:80])
    for attempt in range(max_retries):
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return Image.open(io.BytesIO(r.read())).convert("RGB")
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            retry_after = e.headers.get("Retry-After")
            try:
                wait = float(retry_after) if retry_after else 2 ** (attempt + 1)
            except ValueError:
                wait = 2 ** (attempt + 1)
            log.info("  429 — backing off %.1fs (attempt %d/%d)",
                     wait, attempt + 1, max_retries)
            time.sleep(min(wait, 60.0))
    raise RuntimeError(f"giving up on {url}: rate-limited too many times")


def _sample_background_color(
    im: Image.Image, cx: int, cy: int, inner: int, outer: int,
) -> tuple[int, int, int]:
    """Median RGB inside the annulus around (cx, cy)."""
    px = im.load()
    samples_r: list[int] = []
    samples_g: list[int] = []
    samples_b: list[int] = []
    w, h = im.size
    inner_sq = inner * inner
    outer_sq = outer * outer
    # Walk the bounding box of the outer ring; cheap enough at our sizes.
    for y in range(max(0, cy - outer), min(h, cy + outer + 1)):
        for x in range(max(0, cx - outer), min(w, cx + outer + 1)):
            d = (x - cx) ** 2 + (y - cy) ** 2
            if d < inner_sq or d > outer_sq:
                continue
            r, g, b = px[x, y]
            samples_r.append(r)
            samples_g.append(g)
            samples_b.append(b)
    if not samples_r:
        return (128, 128, 128)
    samples_r.sort(); samples_g.sort(); samples_b.sort()
    mid = len(samples_r) // 2
    return (samples_r[mid], samples_g[mid], samples_b[mid])


def _surface_hint_from_caption(caption: str) -> str:
    """Infer surface from the photo caption — Flux fill produces
    cleaner output when you tell it what should be there. Madrid /
    Roland Garros / Rome / Monte Carlo are clay; Wimbledon is
    grass; everything else is hard.
    """
    c = (caption or "").lower()
    if any(k in c for k in ("madrid", "roland", "french open", "rome", "monte carlo")):
        return "red clay tennis court surface"
    if "wimbledon" in c:
        return "green grass tennis court surface"
    return "blue hard tennis court surface"


def _ai_inpaint_ball(
    im: Image.Image, ball_x_pct: float, ball_y_pct: float, caption: str,
) -> Image.Image:
    """Replicate Flux fill — context-aware inpainting that actually
    reconstructs the background where the ball was, even when the ball
    overlaps the player's body. Costs ~$0.04 per image.

    Requires REPLICATE_API_TOKEN in env.
    """
    import os
    import replicate

    if not os.environ.get("REPLICATE_API_TOKEN"):
        raise RuntimeError(
            "REPLICATE_API_TOKEN not set — export it before --use-ai",
        )

    w, h = im.size
    cx = int(round(w * ball_x_pct / 100))
    cy = int(round(h * ball_y_pct / 100))
    # Mask radius: generous so the model has room to reconstruct
    # the texture without leaving a halo of original-ball pixels.
    mask_r = max(30, int(round(55 * w / 960)))

    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).ellipse(
        [(cx - mask_r, cy - mask_r), (cx + mask_r, cy + mask_r)],
        fill=255,
    )
    # Light blur on the mask edge so the model blends rather than
    # producing a sharp boundary.
    mask = mask.filter(ImageFilter.GaussianBlur(radius=4))

    img_buf = io.BytesIO()
    im.save(img_buf, "JPEG", quality=92)
    img_buf.seek(0)
    mask_buf = io.BytesIO()
    mask.save(mask_buf, "PNG")
    mask_buf.seek(0)

    surface = _surface_hint_from_caption(caption)
    prompt = (
        f"clean {surface} background, photorealistic, seamless, "
        f"matches the surrounding texture exactly, no objects, no ball"
    )
    log.info("  replicate flux-fill: mask r=%d at (%d,%d) prompt=%r",
             mask_r, cx, cy, surface)

    output = replicate.run(
        "black-forest-labs/flux-fill-dev",
        input={
            "image": img_buf,
            "mask": mask_buf,
            "prompt": prompt,
            "num_inference_steps": 28,
            "guidance": 30,
            "output_format": "jpg",
            "output_quality": 92,
        },
    )

    # SDK returns either a file-like object, a URL string, or a list.
    if isinstance(output, list):
        output = output[0]
    if hasattr(output, "read"):
        data = output.read()
    else:
        with urllib.request.urlopen(str(output)) as r:
            data = r.read()
    return Image.open(io.BytesIO(data)).convert("RGB")


def _inpaint_ball(
    im: Image.Image, ball_x_pct: float, ball_y_pct: float,
) -> Image.Image:
    w, h = im.size
    cx = int(round(w * ball_x_pct / 100.0))
    cy = int(round(h * ball_y_pct / 100.0))
    # Scale ball radius proportionally to image width.
    ball_radius = max(12, int(round(BALL_RADIUS_AT_960 * w / 960)))
    inner = int(round(ball_radius * SAMPLE_INNER_FACTOR))
    outer = int(round(ball_radius * SAMPLE_OUTER_FACTOR))
    bg = _sample_background_color(im, cx, cy, inner, outer)
    log.info("  ball=(%d,%d) r=%d  sampled bg=%s", cx, cy, ball_radius, bg)

    # Painted disc lives on a temporary RGBA layer so we can blur its
    # alpha for the feather, then composite. Simpler than blur+restore
    # tricks; reads cleanly on inspection.
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    # Slightly bigger disc than the ball — accounts for cast shadow.
    paint_r = int(ball_radius * 1.1)
    od.ellipse(
        [(cx - paint_r, cy - paint_r), (cx + paint_r, cy + paint_r)],
        fill=(*bg, 255),
    )
    # Feather edges.
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=FEATHER_RADIUS))
    base = im.convert("RGBA")
    return Image.alpha_composite(base, overlay).convert("RGB")


def _fetch_calibrated_puzzles() -> list[dict]:
    url = f"{API_BASE}/api/spot-the-ball/archive?limit=200"
    with urllib.request.urlopen(url) as r:
        archive = json.load(r)
    # Archive items don't include ball coords — fetch each.
    out = []
    for item in archive:
        with urllib.request.urlopen(
            f"{API_BASE}/api/spot-the-ball/{item['puzzle_date']}",
        ) as r:
            out.append(json.load(r))
    return out


def _prod_update_image_url(puzzle_date: str, new_url: str) -> None:
    """SSH into prod and patch the row. Cheap one-shot — keeps the
    main admin API surface narrow (no image-url endpoint needed)."""
    py = (
        "from sqlmodel import Session, select; "
        "from app.db.session import engine; "
        "from app.models.spot_the_ball import SpotTheBallPuzzle; "
        "from datetime import date; "
        "import sys; "
        f"d = date.fromisoformat({puzzle_date!r}); "
        f"new = {new_url!r}; "
        "s = Session(engine); "
        "row = s.exec(select(SpotTheBallPuzzle).where(SpotTheBallPuzzle.puzzle_date == d)).first(); "
        "row.image_url = new; "
        "s.add(row); s.commit(); "
        "print(f'updated {d} -> {new}')"
    )
    cmd = [
        "ssh", "mobtennis-ubuntu",
        f"cd /opt/tennismob/backend && sudo -u tennismob /opt/tennismob/backend/.venv/bin/python -c {shlex.quote(py)}",
    ]
    res = subprocess.run(cmd, check=True, capture_output=True, text=True)
    log.info("  %s", res.stdout.strip())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--public-base", default="https://mob.tennis",
        help="Public origin where /spot-the-ball/<date>.jpg will be served. "
             "Vercel serves web/public from the site root.",
    )
    parser.add_argument(
        "--skip-db-update", action="store_true",
        help="Process images only; don't touch the prod DB.",
    )
    parser.add_argument(
        "--date", default=None,
        help="Process a single puzzle by ISO date instead of all.",
    )
    parser.add_argument(
        "--use-ai", action="store_true",
        help="Use Replicate Flux fill instead of the Pillow median-sample "
             "fallback. Requires REPLICATE_API_TOKEN. ~$0.04 per image.",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Reprocess puzzles whose image_url already points at our "
             "public origin (i.e. previously processed).",
    )
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    puzzles = _fetch_calibrated_puzzles()
    if args.date:
        puzzles = [p for p in puzzles if p["puzzle_date"] == args.date]
    log.info("processing %d puzzles", len(puzzles))

    import time
    for i, p in enumerate(puzzles):
        d = p["puzzle_date"]
        log.info("[%s] %s", d, p.get("caption", ""))
        if not args.force and p["image_url"].startswith(args.public_base):
            log.info("  already pointing at processed URL; --force to redo")
            continue
        # Prefer the hardcoded original source over the row's image_url
        # because image_url was overwritten with the local path on the
        # first processing pass.
        source = SOURCE_URLS.get(d, p["image_url"])
        if i > 0:
            # Throttle between source downloads to keep Wikimedia happy.
            time.sleep(1.5)
        try:
            im = _download(source)
            if args.use_ai:
                edited = _ai_inpaint_ball(
                    im, p["ball_x_pct"], p["ball_y_pct"], p.get("caption", ""),
                )
            else:
                edited = _inpaint_ball(im, p["ball_x_pct"], p["ball_y_pct"])
        except Exception:
            log.exception("  failed to process %s", d)
            continue
        out_path = OUT_DIR / f"{d}.jpg"
        edited.save(out_path, "JPEG", quality=90)
        log.info("  wrote %s (%d KB)", out_path, out_path.stat().st_size // 1024)
        if not args.skip_db_update:
            new_url = f"{args.public_base}/spot-the-ball/{d}.jpg"
            _prod_update_image_url(d, new_url)


if __name__ == "__main__":
    main()
