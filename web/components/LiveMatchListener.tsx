"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { API_BASE } from "@/lib/api";

type Props = {
  /** Only events for this match id will trigger a refresh. */
  matchId: number;
  /** Skip the listener entirely if the match isn't live (saves a server
   * connection per closed match page). */
  enabled?: boolean;
};

/**
 * Subscribes to /api/stream and triggers `router.refresh()` on every
 * `match.updated` event whose match.id matches the page. Replaces the
 * polling-based AutoRefresh on match detail pages — sub-second updates
 * instead of 10-second polls.
 *
 * Server-render still produces the initial HTML for SEO + first paint;
 * this just keeps it fresh while the user is on the page. router.refresh()
 * preserves React state + scroll position (unlike a full reload).
 *
 * Multiple events per second get debounced — many api-tennis updates are
 * tiny score deltas that don't need their own refresh.
 */
export function LiveMatchListener({ matchId, enabled = true }: Props) {
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
          if (ev?.type === "match.updated" && ev.match?.id === matchId) {
            if (debounce) clearTimeout(debounce);
            debounce = setTimeout(() => router.refresh(), 250);
          }
        } catch {
          /* ignore malformed events */
        }
      };
      es.onerror = () => {
        // EventSource has built-in retry but if the server fully closes,
        // the connection ends. Re-create after a short delay.
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
  }, [enabled, matchId, router]);

  return null;
}
