"use client";

/**
 * Tour preference for joint-tournament disambiguation.
 *
 * The user picks a tour implicitly any time they navigate to one (rankings
 * tab, tour pill on a tournament page). We persist the most recent choice
 * and use it to default the link target on Australian Open, Indian Wells,
 * and other ATP+WTA combined events.
 *
 * Default ATP if nothing's been chosen yet.
 */

import { useEffect, useState } from "react";

import type { Tour } from "@/lib/api";

const KEY = "tennismob:preferred_tour";
const EVENT = "tennismob:preferred_tour_changed";

export function getPreferredTourSync(): Tour {
  if (typeof window === "undefined") return "atp";
  const v = localStorage.getItem(KEY);
  return v === "wta" ? "wta" : "atp";
}

export function setPreferredTour(tour: Tour): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(KEY, tour);
  window.dispatchEvent(new CustomEvent(EVENT));
}

export function usePreferredTour(): { tour: Tour; setTour: (t: Tour) => void } {
  // SSR returns "atp"; the effect rehydrates from localStorage and fires a
  // re-render so links pick up the user's stored choice on the client.
  const [tour, setTourState] = useState<Tour>("atp");
  useEffect(() => {
    setTourState(getPreferredTourSync());
    const handler = () => setTourState(getPreferredTourSync());
    window.addEventListener(EVENT, handler);
    window.addEventListener("storage", handler);
    return () => {
      window.removeEventListener(EVENT, handler);
      window.removeEventListener("storage", handler);
    };
  }, []);

  return {
    tour,
    setTour: (t) => {
      setPreferredTour(t);
      setTourState(t);
    },
  };
}

/** Pick the best tour for a brand given user preference + what's available. */
export function pickTour(preferred: Tour, available: string[] | null | undefined): Tour {
  if (!available || available.length === 0) return preferred;
  if (available.includes(preferred)) return preferred;
  // Stable fallback: atp if it exists, else whichever is there.
  if (available.includes("atp")) return "atp";
  return (available[0] as Tour) ?? "atp";
}
