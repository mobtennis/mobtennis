"""Expo push delivery.

Posts to Expo's public push API (no APNs/FCM credentials needed — Expo
proxies). Best-effort: push failures must never block the live poll.
"""

import logging

import httpx

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"

log = logging.getLogger(__name__)


async def send_push(messages: list[dict]) -> None:
    """Send a batch of Expo push messages.

    Each message: {"to": expo_token, "title": str, "body": str, "data": dict}.
    Expo accepts up to 100 messages per request — we chunk accordingly.
    """
    if not messages:
        return
    async with httpx.AsyncClient(timeout=10.0) as client:
        for i in range(0, len(messages), 100):
            chunk = messages[i:i + 100]
            try:
                resp = await client.post(
                    EXPO_PUSH_URL,
                    json=chunk,
                    headers={
                        "Accept": "application/json",
                        "Accept-Encoding": "gzip, deflate",
                        "Content-Type": "application/json",
                    },
                )
                if resp.status_code >= 400:
                    log.warning("expo push %s: %s", resp.status_code, resp.text[:300])
            except Exception:
                log.exception("expo push send failed")
