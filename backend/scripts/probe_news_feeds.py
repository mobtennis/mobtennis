"""Probe a list of RSS feeds and report per-feed entry counts.

Uses feedparser (same as sync_news) so the results reflect what we'd
actually ingest, not just whether the URL responds. A feed that
returns HTML or an empty XML is treated as broken even when the URL
returns 200.

Usage:
  sudo -u tennismob /opt/tennismob/backend/.venv/bin/python \\
    /opt/tennismob/backend/scripts/probe_news_feeds.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _load_env_file() -> None:
    env_file = Path(__file__).resolve().parents[1] / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env_file()

import feedparser  # noqa: E402


CANDIDATES: list[tuple[str, str]] = [
    # Current production feeds
    ("atptour",            "https://www.atptour.com/en/media/rss-feed/xml-feed"),
    ("wta",                "https://www.wtatennis.com/rss/news"),
    ("tennis.com",         "https://www.tennis.com/feed/"),
    ("reuters",            "https://www.reutersagency.com/feed/?best-topics=sports&post_type=best"),
    ("espn",               "https://www.espn.com/espn/rss/tennis/news"),
    ("the-tennis-podcast", "https://thetennispodcast.libsyn.com/rss"),
    # Proposed replacements / additions
    ("guardian",           "https://www.theguardian.com/sport/tennis/rss"),
    ("bbc",                "https://feeds.bbci.co.uk/sport/tennis/rss.xml"),
    ("nyt",                "https://rss.nytimes.com/services/xml/rss/nyt/Tennis.xml"),
    ("tennis365",          "https://www.tennis365.com/feed"),
]


def probe(source: str, url: str) -> dict:
    out: dict = {"source": source, "url": url, "entries": 0, "verdict": "", "title": None}
    try:
        feed = feedparser.parse(url)
    except Exception as e:
        out["verdict"] = f"crash: {type(e).__name__}: {e}"
        return out
    out["entries"] = len(feed.entries)
    out["title"] = (feed.feed.get("title") if hasattr(feed, "feed") else None) or None
    status = getattr(feed, "status", None)
    bozo = bool(getattr(feed, "bozo", False))
    if status and status >= 400:
        out["verdict"] = f"http {status}"
    elif out["entries"] == 0:
        out["verdict"] = f"empty (status {status}, bozo={bozo})"
    elif bozo and status not in (200, 301, 302, None):
        out["verdict"] = f"degraded (status {status}, bozo)"
    else:
        out["verdict"] = f"ok (status {status})"
    return out


def main() -> None:
    print(f"{'source':22} {'entries':>7}  {'verdict':40} title")
    print("-" * 110)
    for source, url in CANDIDATES:
        r = probe(source, url)
        title = (r["title"] or "")[:35]
        print(f"{r['source']:22} {r['entries']:>7}  {r['verdict']:40} {title}")


if __name__ == "__main__":
    main()
