"""Tests for the api-tennis provider — focused on the regressions
we've actually hit, so they stop recurring.
"""

from __future__ import annotations

import pytest

from app.services.live.api_tennis import ApiTennisProvider


class _MockResponse:
    def __init__(self, json_payload: dict):
        self._json = json_payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._json


class _MockClient:
    """Captures every outbound request so we can assert on params."""

    def __init__(self):
        self.calls: list[dict] = []

    async def get(self, url: str, params: dict):
        self.calls.append({"url": url, "params": dict(params)})
        return _MockResponse({"success": 1, "result": []})

    async def aclose(self):
        pass


@pytest.mark.asyncio
async def test_call_passes_timezone_utc():
    """Every REST call must include timezone=UTC. Otherwise api-tennis
    returns event_date/event_time in the venue's local timezone, which
    we then store as if it were UTC and end up displaying matches 1–3
    hours off depending on the venue (Rome 19:00 CEST = 17:00 UTC).
    Caught in prod when a Rome QF showed up at 19:00 instead of 17:00.
    """
    p = ApiTennisProvider("test-key", base_url="https://api.test")
    p._client = _MockClient()  # type: ignore[assignment]
    await p.fetch_today()
    assert len(p._client.calls) == 1  # type: ignore[attr-defined]
    params = p._client.calls[0]["params"]  # type: ignore[attr-defined]
    assert params.get("timezone") == "UTC", (
        f"REST call missing timezone=UTC: {params}"
    )


@pytest.mark.asyncio
async def test_call_passes_timezone_utc_on_live():
    p = ApiTennisProvider("test-key", base_url="https://api.test")
    p._client = _MockClient()  # type: ignore[assignment]
    await p.fetch_live()
    params = p._client.calls[0]["params"]  # type: ignore[attr-defined]
    assert params.get("timezone") == "UTC"
