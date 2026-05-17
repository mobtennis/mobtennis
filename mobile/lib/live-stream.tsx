/**
 * Subscribe to /api/stream and invalidate the affected TanStack Query
 * caches when match.updated events arrive. Mounted once at the root —
 * every screen using `useQuery(["matches-live"])`, `["match", id]`, etc.
 * gets sub-second updates without per-screen wiring.
 *
 * Uses react-native-sse (pure-JS XHR-based polyfill) so this works in
 * Expo Go without needing a custom dev client.
 *
 * We still keep refetchInterval as a fallback in case the stream is
 * down — but with this in place, we can relax those intervals.
 */

import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import RNEventSource from "react-native-sse";

import { API_BASE } from "@/lib/api";

const RECONNECT_MS = 3000;

export function LiveStreamSubscriber() {
  const qc = useQueryClient();

  useEffect(() => {
    let es: RNEventSource | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let cancelled = false;

    // Only invalidate the specific match's query — never the list queries.
    // api-tennis pushes 5–10 score updates per second; if we invalidated
    // every list query (matches-live, tournaments-index, …) on each event,
    // each phone would fire 10× refetches/second of multi-second endpoints
    // and quickly exhaust the backend's connection pool. The lists keep
    // refreshing on their own polling cadence (60–90s); the SSE path is
    // only here to keep an open match-detail page live to the second.
    const handleMatchUpdate = (matchId: number) => {
      qc.invalidateQueries({ queryKey: ["match", String(matchId)] });
      qc.invalidateQueries({ queryKey: ["match", matchId] });
    };

    const connect = () => {
      if (cancelled) return;
      es = new RNEventSource(`${API_BASE.replace(/\/$/, "")}/api/stream`);

      es.addEventListener("message", (event) => {
        try {
          const data = (event as { data?: string }).data;
          if (!data) return;
          const ev = JSON.parse(data);
          if (ev?.type === "match.updated" && ev.match?.id != null) {
            handleMatchUpdate(Number(ev.match.id));
          }
        } catch {
          /* ignore malformed events */
        }
      });

      es.addEventListener("error", () => {
        es?.close();
        es = null;
        if (!cancelled && !reconnectTimer) {
          reconnectTimer = setTimeout(() => {
            reconnectTimer = null;
            connect();
          }, RECONNECT_MS);
        }
      });
    };

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      es?.close();
    };
  }, [qc]);

  return null;
}
