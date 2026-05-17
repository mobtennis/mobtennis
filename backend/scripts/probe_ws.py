"""Connect to api-tennis WebSocket and dump everything that arrives for
30 seconds. Use to figure out the wire protocol — whether the server
pushes events on connect, requires a subscribe handshake, sends pings, etc.

Usage on the box:
  ssh mobtennis-ubuntu '\\
    sudo -u tennismob \\
    /opt/tennismob/backend/.venv/bin/python \\
    /opt/tennismob/backend/scripts/probe_ws.py'
"""

from __future__ import annotations

import asyncio
import os
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

from app.config import settings  # noqa: E402


async def main() -> None:
    if not settings.api_tennis_key:
        print("API_TENNIS_KEY missing — set in .env")
        return

    import websockets

    url = (
        f"{settings.api_tennis_ws_url}"
        f"?APIkey={settings.api_tennis_key}&timezone=UTC"
    )
    print(f"connecting to {settings.api_tennis_ws_url}")

    async with websockets.connect(url, ping_interval=30, ping_timeout=10) as ws:
        print("connected — listening for 30s")

        async def reader() -> None:
            async for raw in ws:
                preview = raw if isinstance(raw, str) else f"<bytes len={len(raw)}>"
                if len(preview) > 500:
                    preview = preview[:500] + "..."
                print(f"<< {preview}")

        try:
            await asyncio.wait_for(reader(), timeout=30)
        except asyncio.TimeoutError:
            print("(30s elapsed, exiting)")


if __name__ == "__main__":
    asyncio.run(main())
