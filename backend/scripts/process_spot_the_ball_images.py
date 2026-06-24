"""Run Replicate Flux fill on pool images, save inpainted JPGs to
web/public/spot-the-ball/, flip is_inpainted=True on each row.

The bundler (in services/spot_the_ball_bundler.py) groups inpainted
pool images into sets of 5 at the next admin queue-page view, so
the queue → process → bundle pipeline runs itself once you push the
output of this script.

Usage:
  REPLICATE_API_TOKEN=… ADMIN_KEY=… \
      python -m scripts.process_spot_the_ball_images
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import os
import shlex
import subprocess
import time
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("process_stb")

API_BASE = "https://api.mob.tennis"
ADMIN_KEY = os.environ.get("ADMIN_KEY", "")
REPO_ROOT = Path(__file__).resolve().parents[2]
# Local staging dir for the JPGs before scp to prod. Kept in the repo
# root rather than a temp dir so failed runs leave inspectable
# artifacts (and a repeat-after-fix doesn't have to re-pay Replicate).
# Git ignores this path — see web/.gitignore.
OUT_DIR = REPO_ROOT / "web" / "public" / "spot-the-ball"

# Where the inpainted JPGs land on the Lightsail box. Caddy serves
# this directory at https://api.mob.tennis/spot-the-ball/{id}.jpg.
PROD_HOST = "mobtennis-ubuntu"
PROD_ASSET_DIR = "/opt/tennismob/data/spot-the-ball"

# Mask radius (px at 960px source width) bumps 20% per attempt so a
# rejected inpaint gets a fatter mask on retry — gives the model more
# room to reconstruct the background.
BASE_MASK_RADIUS_AT_960 = 55
MASK_RADIUS_GROWTH_PER_ATTEMPT = 0.20

# Polite default; Wikimedia rate-limits hard.
INTER_DOWNLOAD_SLEEP = 1.5


def _download(url: str, max_retries: int = 5) -> Image.Image:
    log.info("  downloading %s", url[:80])
    for attempt in range(max_retries + 1):
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


def _surface_hint_from_caption(caption: str) -> str:
    c = (caption or "").lower()
    if any(k in c for k in ("madrid", "roland", "french open", "rome", "monte carlo")):
        return "red clay tennis court surface"
    if "wimbledon" in c:
        return "green grass tennis court surface"
    return "blue hard tennis court surface"


def _ai_inpaint(
    im: Image.Image,
    ball_x_pct: float,
    ball_y_pct: float,
    caption: str,
    mask_radius_factor: float,
) -> Image.Image:
    """Replicate Flux fill with a player-context-aware prompt."""
    import replicate

    if not os.environ.get("REPLICATE_API_TOKEN"):
        raise RuntimeError("REPLICATE_API_TOKEN not set")

    w, h = im.size
    cx = int(round(w * ball_x_pct / 100))
    cy = int(round(h * ball_y_pct / 100))
    mask_r = max(30, int(round(BASE_MASK_RADIUS_AT_960 * mask_radius_factor * w / 960)))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).ellipse(
        [(cx - mask_r, cy - mask_r), (cx + mask_r, cy + mask_r)],
        fill=255,
    )
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
    log.info("  flux-fill: mask r=%d (factor %.2f) at (%d,%d)",
             mask_r, mask_radius_factor, cx, cy)

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
    if isinstance(output, list):
        output = output[0]
    if hasattr(output, "read"):
        data = output.read()
    else:
        with urllib.request.urlopen(str(output)) as r:
            data = r.read()
    return Image.open(io.BytesIO(data)).convert("RGB")


def _fetch_pool() -> list[dict]:
    """Every image that needs inpainting — pool members not yet
    processed PLUS already-bundled images the admin rejected. Backend
    returns this combined list as `images_needing_inpaint` so the
    reject-then-re-process loop works without us having to think
    about set membership here."""
    if not ADMIN_KEY:
        raise RuntimeError("ADMIN_KEY env var required")
    with urllib.request.urlopen(
        f"{API_BASE}/api/admin/spot-the-ball/queue?key={ADMIN_KEY}",
    ) as r:
        data = json.load(r)
    return list(data.get("images_needing_inpaint", []))


def _scp_to_prod(local_path: Path, image_id: int) -> None:
    """Copy the inpainted JPG to the box. Caddy serves the directory
    at https://api.mob.tennis/spot-the-ball/{id}.jpg, so once this
    lands the public URL is reachable. Idempotent — scp overwrites.
    """
    # We use a relay through sudo-as-tennismob so the file ends up
    # owned by the same user Caddy + the FastAPI app run as.
    cmd_mkdir = [
        "ssh", PROD_HOST,
        f"sudo -u tennismob mkdir -p {PROD_ASSET_DIR}",
    ]
    subprocess.run(cmd_mkdir, check=True, capture_output=True, text=True)

    # scp can't write directly as another user; stage in /tmp, then mv.
    remote_staging = f"/tmp/stb-{image_id}.jpg"
    subprocess.run(
        ["scp", "-q", str(local_path), f"{PROD_HOST}:{remote_staging}"],
        check=True, capture_output=True, text=True,
    )
    subprocess.run(
        [
            "ssh", PROD_HOST,
            f"sudo install -o tennismob -g tennismob -m 644 "
            f"{remote_staging} {PROD_ASSET_DIR}/{image_id}.jpg "
            f"&& rm -f {remote_staging}",
        ],
        check=True, capture_output=True, text=True,
    )


def _prod_update(image_id: int, new_image_url: str) -> None:
    """SSH into prod: flip is_inpainted=True, update image_url to local,
    increment inpaint_attempts."""
    py = (
        "from sqlmodel import Session, select; "
        "from app.db.session import engine; "
        "from app.models.spot_the_ball import SpotTheBallImage; "
        f"image_id = {image_id}; "
        f"new = {new_image_url!r}; "
        "s = Session(engine); "
        "img = s.exec(select(SpotTheBallImage).where(SpotTheBallImage.id == image_id)).first(); "
        "img.image_url = new; "
        "img.is_inpainted = True; "
        "img.inpaint_attempts = (img.inpaint_attempts or 0) + 1; "
        "img.inpaint_rejected_at = None; "
        "s.add(img); s.commit(); "
        "print(f'updated {image_id}: inpainted, attempts={img.inpaint_attempts}')"
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
        "--id", type=int, default=None,
        help="Process a single image by id (default: walk the whole pool).",
    )
    parser.add_argument(
        "--public-base", default=API_BASE,
        help="Public origin where /spot-the-ball/{id}.jpg is served. "
             "Defaults to api.mob.tennis — Caddy on the Lightsail box "
             "serves the directory directly, so no Vercel deploy needed.",
    )
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pool = _fetch_pool()
    if args.id:
        pool = [p for p in pool if p["id"] == args.id]
    log.info("processing %d pool image(s)", len(pool))

    for i, p in enumerate(pool):
        img_id = p["id"]
        log.info("[image #%d] %s", img_id, p["caption"])
        source = p["original_image_url"] or p["image_url"]
        if i > 0:
            time.sleep(INTER_DOWNLOAD_SLEEP)
        try:
            im = _download(source)
            # Bump mask each retry so a previously-rejected attempt
            # gets a fatter mask this time.
            attempt_idx = p.get("inpaint_attempts", 0)
            factor = 1.0 + attempt_idx * MASK_RADIUS_GROWTH_PER_ATTEMPT
            edited = _ai_inpaint(
                im, p["ball_x_pct"], p["ball_y_pct"], p["caption"], factor,
            )
        except Exception:
            log.exception("  failed image #%d", img_id)
            continue
        out_path = OUT_DIR / f"{img_id}.jpg"
        edited.save(out_path, "JPEG", quality=90)
        log.info("  wrote %s (%d KB)", out_path, out_path.stat().st_size // 1024)
        try:
            _scp_to_prod(out_path, img_id)
        except subprocess.CalledProcessError as e:
            log.error("  scp to prod failed: %s", e.stderr or e.stdout)
            continue
        new_url = f"{args.public_base}/spot-the-ball/{img_id}.jpg"
        _prod_update(img_id, new_url)


if __name__ == "__main__":
    main()
