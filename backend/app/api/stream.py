"""Server-Sent Events stream of live match updates.

Backend WS consumer publishes to the in-memory `live_hub`; this endpoint
streams those events to subscribed browsers as SSE. Clients use the
standard EventSource API:

    const es = new EventSource("https://api.mob.tennis/api/stream");
    es.onmessage = (e) => {
      const ev = JSON.parse(e.data);
      if (ev.type === "match.updated" && ev.match.id === MY_MATCH) ...
    };

Heartbeat every ~20s so proxies don't close idle connections.

Why connections are bounded by lifetime instead of trusting
disconnect detection: with Caddy in front of uvicorn, an
ungracefully-disconnected client (mobile network drop, tab close
without close frame) can leave uvicorn with a half-open socket.
Caddy buffers our heartbeats; uvicorn never sees an http.disconnect
message; `request.is_disconnected()` returns False forever. The
generator sits there holding a 200-slot queue, indefinitely. Twice
in one afternoon this leaked enough state to OOM the box.

`MAX_AGE_S` caps any single connection's lifetime. EventSource
auto-reconnects in 3s, so this is invisible to the user — but each
zombie connection's footprint disappears within the window.

`MAX_SUBSCRIBERS` is the hard safety net for traffic spikes: refuse
new subscribers with 503 rather than accept-and-OOM. The browser
will retry shortly.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

from fastapi import APIRouter, Request
from fastapi.responses import Response, StreamingResponse

from app.services.live_hub import hub

router = APIRouter(prefix="/api", tags=["stream"])
log = logging.getLogger(__name__)

# Heartbeat interval. Must be < the shortest idle-timeout of any proxy
# in front of us (Caddy default reverse_proxy read is 60s); 20s leaves
# room.
_HEARTBEAT_S = 20

# Hard cap on a single connection's lifetime. After this the server
# closes the stream cleanly and the browser's EventSource reconnects
# (~3 s). Bounds the cost of stale half-open connections that we never
# detected as disconnected.
MAX_AGE_S = 5 * 60

# Hard cap on concurrent subscribers. If we ever blow past this, the
# server is unhealthy or under attack and accepting more connections
# only digs the hole deeper.
MAX_SUBSCRIBERS = 200


@router.get("/stream")
async def stream(request: Request):
    if hub.subscriber_count >= MAX_SUBSCRIBERS:
        log.warning("sse: refusing new subscriber (count=%d)", hub.subscriber_count)
        return Response(status_code=503, content="too many subscribers, retry shortly")

    queue = hub.subscribe()
    started_at = time.monotonic()
    log.info("sse subscribe: total=%d", hub.subscriber_count)

    async def gen():
        try:
            yield ": connected\n\n"
            while True:
                # Bounded lifetime — see module docstring.
                age = time.monotonic() - started_at
                if age >= MAX_AGE_S:
                    break
                # Cheap disconnect check between events; not relied upon
                # for cleanup correctness, but exits faster when it works.
                if await request.is_disconnected():
                    break

                # Cap the queue wait at whichever comes first: the
                # heartbeat tick or the remaining connection lifetime.
                wait = min(_HEARTBEAT_S, MAX_AGE_S - age)
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=wait)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        except asyncio.CancelledError:
            # Client closed cleanly; let the finally run.
            pass
        finally:
            hub.unsubscribe(queue)
            log.info(
                "sse unsubscribe: total=%d age=%.1fs",
                hub.subscriber_count,
                time.monotonic() - started_at,
            )

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
