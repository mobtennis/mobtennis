"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { API_BASE } from "@/lib/api";

/**
 * Connects to /api/stream and triggers `router.refresh()` on every
 * `match.updated` event, no matter which match. Used on pages that
 * show *many* live matches at once (home, tournament, player) where
 * we don't want to filter by match id but do want sub-second updates
 * to scoreline UI instead of a 30-second polling tick.
 *
 * Debounce is intentionally longer than the per-match listener: many
 * api-tennis events fire per second across all live matches, and we
 * don't need to refresh the whole tree more than ~once a second to
 * feel "live."
 *
 * router.refresh() preserves React state + scroll position and
 * re-runs only the server components, so the cost is bounded by the
 * server fetch cache TTLs (kept short for `/api/matches/live` so the
 * refresh actually returns fresh data).
 */
/**
 * Always-on by default. Earlier we accepted an `enabled` prop derived
 * from "does the page currently have live matches?", but that gating
 * was sticky — once it went false (e.g. when the last match of the
 * evening ended), the SSE listener never reconnected within the same
 * page session, and new matches starting later didn't trigger any
 * refresh. EventSource is cheap (one connection per tab); keeping it
 * always open is the right trade.
 */
export function LiveStreamRefresh({ enabled = true }: { enabled?: boolean }) {
  const router = useRouter();

  useEffect(() => {
    if (!enabled) return;

    const url = `${API_BASE}/api/stream`;
    let es: EventSource | null = null;
    let debounce: ReturnType<typeof setTimeout> | null = null;
    let reconnect: ReturnType<typeof setTimeout> | null = null;

    const connect = () => {
      es = new EventSource(url);
      es.onmessage = (e) => {
        try {
          const ev = JSON.parse(e.data);
          if (ev?.type === "match.updated") {
            if (debounce) clearTimeout(debounce);
            debounce = setTimeout(() => router.refresh(), 1500);
          }
        } catch {
          /* ignore malformed events */
        }
      };
      es.onerror = () => {
        es?.close();
        es = null;
        if (!reconnect) {
          reconnect = setTimeout(() => {
            reconnect = null;
            connect();
          }, 3000);
        }
      };
    };

    connect();

    return () => {
      if (debounce) clearTimeout(debounce);
      if (reconnect) clearTimeout(reconnect);
      es?.close();
    };
  }, [enabled, router]);

  return null;
}
