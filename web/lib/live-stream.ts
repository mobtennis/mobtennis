"use client";

import { useEffect, useSyncExternalStore } from "react";

import { API_BASE, type MatchSummary } from "@/lib/api";

/**
 * Single shared EventSource per browser tab, with fan-out to any
 * component that subscribes to a specific match id.
 *
 * Why not `router.refresh()` from every listener: refreshing pipes
 * every score update through a Next.js RSC round-trip whose fetch
 * cache (Data Cache) respects the page's `revalidate` value. With
 * the match detail page previously set to `revalidate: 10`, score
 * updates could sit stale for up to 10s per refresh; Next 15's
 * router cache staleTimes could stretch that further in some
 * navigations. Pushing MatchSummary from the SSE event straight
 * into React state gives sub-second updates and skips the entire
 * caching stack.
 *
 * The connection is lazy — first subscribe opens it, last
 * unsubscribe closes it. EventSource auto-reconnects on 5xx /
 * network blips.
 */

type Handler = (m: MatchSummary) => void;

let source: EventSource | null = null;
// Per-match handlers. A Set so multiple components on the same
// match id (e.g. hover card + match card) get parallel updates.
const handlers = new Map<number, Set<Handler>>();
// Last-seen snapshot for each match id. New subscribers get the
// most recent value synchronously so mounting a component with an
// SSE-provided snapshot from a moment ago doesn't wait for the
// next event to hydrate.
const latest = new Map<number, MatchSummary>();
// Global subscribers to "any match updated" — used by pages that
// want to know a payload arrived (usually to trigger local
// re-derivations that don't map to a single match id).
const anyHandlers = new Set<() => void>();


function ensureOpen(): void {
  if (source) return;
  if (typeof window === "undefined") return;
  const es = new EventSource(`${API_BASE}/api/stream`);
  es.onmessage = (e) => {
    let ev: unknown;
    try { ev = JSON.parse(e.data); } catch { return; }
    if (!ev || typeof ev !== "object") return;
    const evTyped = ev as { type?: string; match?: MatchSummary };
    if (evTyped.type !== "match.updated" || !evTyped.match) return;
    const m = evTyped.match;
    latest.set(m.id, m);
    const list = handlers.get(m.id);
    if (list) {
      for (const h of list) {
        try { h(m); } catch { /* ignore consumer errors */ }
      }
    }
    for (const h of anyHandlers) {
      try { h(); } catch { /* ignore */ }
    }
  };
  es.onerror = () => {
    // EventSource auto-reconnects; nothing to do here. If we ever
    // hit MAX_AGE_S on the server it re-establishes a fresh one.
  };
  source = es;
}


function maybeClose(): void {
  if (!source) return;
  if (handlers.size === 0 && anyHandlers.size === 0) {
    source.close();
    source = null;
  }
}


function subscribeMatch(id: number, h: Handler): () => void {
  let set = handlers.get(id);
  if (!set) {
    set = new Set();
    handlers.set(id, set);
  }
  set.add(h);
  ensureOpen();
  // Deliver the last-known snapshot synchronously if we have one.
  const snap = latest.get(id);
  if (snap) {
    // Schedule to run after subscribeMatch returns so callers see
    // the returned unsubscribe function before receiving events.
    Promise.resolve().then(() => h(snap));
  }
  return () => {
    const s = handlers.get(id);
    if (s) {
      s.delete(h);
      if (s.size === 0) handlers.delete(id);
    }
    maybeClose();
  };
}


/**
 * Subscribe to updates for a single match id. Returns the freshest
 * MatchSummary if one has been delivered since page load — else
 * null; the caller supplies its own initial value.
 *
 * Uses useSyncExternalStore so React batches multiple concurrent
 * subscribers without extra state.
 */
export function useLiveMatch(id: number | null): MatchSummary | null {
  const subscribe = (cb: () => void) => {
    if (id == null) return () => {};
    return subscribeMatch(id, () => cb());
  };
  const getSnapshot = () => (id != null ? latest.get(id) ?? null : null);
  const getServerSnapshot = () => null;
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}


/**
 * Fire `handler` whenever ANY match update arrives. For pages that
 * want to know "something changed" without caring which match.
 */
export function useAnyMatchUpdate(handler: () => void): void {
  useEffect(() => {
    if (typeof window === "undefined") return;
    anyHandlers.add(handler);
    ensureOpen();
    return () => {
      anyHandlers.delete(handler);
      maybeClose();
    };
  }, [handler]);
}
