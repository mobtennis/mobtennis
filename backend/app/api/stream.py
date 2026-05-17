"""Server-Sent Events stream of live match updates.

Backend WS consumer publishes to the in-memory `live_hub`; this endpoint
streams those events to subscribed browsers as SSE. Clients use the
standard EventSource API:

    const es = new EventSource("https://api.mob.tennis/api/stream");
    es.onmessage = (e) => {
      const ev = JSON.parse(e.data);
      if (ev.type === "match.updated" && ev.match.id === MY_MATCH) ...
    };

We send a heartbeat comment every ~20s so Caddy/Vercel/proxies don't
close idle connections.
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.services.live_hub import hub

router = APIRouter(prefix="/api", tags=["stream"])
log = logging.getLogger(__name__)

# How long we wait on the queue before sending a heartbeat. Must be < the
# shortest idle-timeout of any proxy in front of us. Caddy default is 60s
# for reverse_proxy reads; 20s gives us headroom.
_HEARTBEAT_S = 20


@router.get("/stream")
async def stream(request: Request) -> StreamingResponse:
    queue = hub.subscribe()

    async def gen():
        try:
            # Initial comment flushes headers and establishes the stream.
            yield ": connected\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_S)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            hub.unsubscribe(queue)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            # Defensive — make sure no layer caches or buffers SSE.
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
