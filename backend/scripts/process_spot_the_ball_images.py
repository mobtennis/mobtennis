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
        if p["image_url"].startswith(args.public_base):
            log.info("  already pointing at processed URL; reprocessing source not yet supported, skipping")
            continue
        if i > 0:
            # Throttle between source downloads to keep Wikimedia happy.
            time.sleep(1.5)
        try:
            im = _download(p["image_url"])
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
