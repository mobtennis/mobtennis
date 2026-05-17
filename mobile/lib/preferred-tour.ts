/**
 * Tour preference for joint-tournament disambiguation.
 *
 * Persisted in SecureStore (iOS Keychain / Android Keystore). Anywhere the
 * user picks a tour explicitly — Rankings tab, tour pill on a tournament
 * detail header — we update this so the next time they tap a joint event
 * (Australian Open, Indian Wells, etc.) the link defaults to that tour.
 *
 * Default ATP if nothing's been chosen yet.
 */

import * as SecureStore from "expo-secure-store";
import { useEffect, useState } from "react";

import type { Tour } from "@/lib/api";

const KEY = "mobtennis.preferred_tour";

let _cached: Tour = "atp";
let _hydrated = false;
const _listeners = new Set<(t: Tour) => void>();

async function _hydrate(): Promise<void> {
  if (_hydrated) return;
  try {
    const v = await SecureStore.getItemAsync(KEY);
    if (v === "wta" || v === "atp") _cached = v;
  } catch {
    // SecureStore is unavailable in some test contexts; default to atp.
  }
  _hydrated = true;
}

export async function setPreferredTour(tour: Tour): Promise<void> {
  _cached = tour;
  _hydrated = true;
  for (const fn of _listeners) fn(tour);
  try {
    await SecureStore.setItemAsync(KEY, tour);
  } catch {
    /* best effort */
  }
}

export function usePreferredTour(): { tour: Tour; setTour: (t: Tour) => void } {
  const [tour, setTourState] = useState<Tour>(_cached);

  useEffect(() => {
    let cancelled = false;
    _hydrate().then(() => {
      if (!cancelled) setTourState(_cached);
    });
    const fn = (t: Tour) => setTourState(t);
    _listeners.add(fn);
    return () => {
      cancelled = true;
      _listeners.delete(fn);
    };
  }, []);

  return {
    tour,
    setTour: (t) => {
      void setPreferredTour(t);
    },
  };
}

export function pickTour(preferred: Tour, available: string[] | null | undefined): Tour {
  if (!available || available.length === 0) return preferred;
  if (available.includes(preferred)) return preferred;
  if (available.includes("atp")) return "atp";
  return (available[0] as Tour) ?? "atp";
}
