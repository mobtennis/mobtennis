"use client";

import { useEffect } from "react";

import { analytics } from "@/lib/analytics-client";

/**
 * Boots the analytics client once at app mount. Rendered from the root
 * layout — returns null, no UI. Safe when keys are unset (noop client).
 */
export function AnalyticsInit() {
  useEffect(() => {
    analytics.init();
  }, []);
  return null;
}
