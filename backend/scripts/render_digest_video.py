"""Render a digest to a vertical MP4 (TikTok/Reels/Shorts format).

Pulls the digest payload from the live API (so a local DB isn't
required) and writes the MP4 to /tmp by default.

Usage:
  python scripts/render_digest_video.py 2026-05-31
  python scripts/render_digest_video.py 2026-05-31 --output ~/Desktop/digest.mp4
  python scripts/render_digest_video.py --latest

Requires `ffmpeg` on PATH and Pillow installed in the active venv.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

from app.services.digest_video import render_digest_video


API_BASE = "https://api.mob.tennis"


def _fetch(path: str) -> dict:
    with urllib.request.urlopen(f"{API_BASE}{path}") as r:
        return json.load(r)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("week", nargs="?", help="Anchor date, e.g. 2026-05-31")
    g.add_argument(
        "--latest", action="store_true",
        help="Render the most recent digest.",
    )
    p.add_argument(
        "--output", default=None,
        help="Output MP4 path. Defaults to /tmp/digest-<week>.mp4",
    )
    args = p.parse_args()

    if args.latest:
        digest = _fetch("/api/digests/latest")
    else:
        digest = _fetch(f"/api/digests/{args.week}")

    week = digest["week_start"]
    print(f"Digest {week}: {digest['headline']!r}")

    out = (
        Path(args.output).expanduser()
        if args.output
        else Path(f"/tmp/digest-{week}.mp4")
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"Rendering to {out} …")
    render_digest_video(digest, out)
    size_kb = out.stat().st_size / 1024
    print(f"DONE — {out} ({size_kb:.0f} KB)")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as e:
        print(f"API error: {e}", file=sys.stderr)
        sys.exit(1)
