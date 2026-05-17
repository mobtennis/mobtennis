"use client";

import { useEffect, useRef } from "react";

import { analytics } from "@/lib/analytics-client";
import type { EventName } from "@/lib/analytics";

/**
 * Fires one analytics event on first mount. Useful for tagging
 * destination pages (match detail, tournament detail, player detail)
 * with structured properties beyond the raw pageview event.
 *
 * Renders nothing. We guard against double-firing on React strict-mode
 * remounts via a ref so the same page navigation never sends two events.
 */
export function TrackOnMount({
  event,
  properties,
}: {
  event: EventName;
  properties?: Record<string, unknown>;
}) {
  const fired = useRef(false);
  useEffect(() => {
    if (fired.current) return;
    fired.current = true;
    analytics.track(event, properties);
  }, [event, properties]);
  return null;
}
