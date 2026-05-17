"""Lightweight Wikipedia client for tournament enrichment.

Uses the public action API for search and the REST v1 summary endpoint for
content. No auth, but Wikipedia asks for a meaningful User-Agent — we send
one. Polite by default: callers should rate-limit (~500ms between calls).
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

UA = "Tennismob/0.1 (https://tennismob.app; bot@mob.tennis)"
SEARCH_URL = "https://en.wikipedia.org/w/api.php"
SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary"


@dataclass
class WikipediaPage:
    title: str
    description: str | None  # short tag like "Tennis tournament held in London"
    extract: str | None      # lead paragraph
    image_url: str | None
    page_url: str | None


async def fetch_summary(query: str, client: httpx.AsyncClient | None = None) -> WikipediaPage | None:
    """Search → summary. Returns None if no good match."""
    own = client is None
    if own:
        client = httpx.AsyncClient(headers={"User-Agent": UA}, timeout=10.0)
    try:
        # 1. Search for the most likely article title
        sr = await client.get(
            SEARCH_URL,
            params={
                "action": "query", "list": "search",
                "srsearch": query, "srlimit": 1, "format": "json",
            },
        )
        sr.raise_for_status()
        hits = sr.json().get("query", {}).get("search", [])
        if not hits:
            return None
        title = hits[0]["title"]

        # 2. Fetch the page summary
        title_url = title.replace(" ", "_")
        pr = await client.get(f"{SUMMARY_URL}/{title_url}")
        if pr.status_code != 200:
            return None
        d = pr.json()
        if d.get("type") == "disambiguation":
            return None
        original = d.get("originalimage") or {}
        thumb = d.get("thumbnail") or {}
        return WikipediaPage(
            title=d.get("title") or title,
            description=d.get("description") or None,
            extract=(d.get("extract") or "").strip() or None,
            image_url=(original.get("source") or thumb.get("source")) or None,
            page_url=(d.get("content_urls", {}).get("desktop", {}).get("page")) or None,
        )
    finally:
        if own:
            await client.aclose()
