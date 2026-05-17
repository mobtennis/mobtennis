"""In-memory event hub for fanning live match updates out to SSE clients.

The WebSocket consumer in scheduler.py publishes a small dict to this hub
after each upsert; the SSE endpoint subscribes and streams events to the
browser. We don't persist anything — clients reconnect to /api/stream
on disconnect and pick up the next event whenever it arrives.

Single-process by design (one uvicorn worker, see tennismob.service).
If we ever scale out the box we'll need Redis pub/sub here.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

# Per-subscriber buffer. Bounded so a slow client doesn't bloat memory —
# if it can't keep up we drop oldest events to make room.
_QUEUE_SIZE = 200


@dataclass
class LiveHub:
    queues: list[asyncio.Queue] = field(default_factory=list)

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=_QUEUE_SIZE)
        self.queues.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self.queues:
            self.queues.remove(q)

    @property
    def subscriber_count(self) -> int:
        return len(self.queues)

    def publish(self, event: dict) -> None:
        """Non-blocking fan-out. Drops oldest event for any slow consumer."""
        for q in list(self.queues):  # copy — list may mutate during iteration
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass


# Module-level singleton — imported by both the publisher (scheduler) and
# the subscriber (api/stream.py).
hub = LiveHub()
