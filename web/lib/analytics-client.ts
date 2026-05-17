"use client";

/**
 * PostHog implementation of AnalyticsClient. Exposes a module-level
 * `analytics` singleton so call-sites import once and don't have to
 * pass it around.
 *
 * When the public key isn't set (dev / preview / contributor without
 * credentials), we fall back to the noop client so the app still
 * builds and runs.
 */

import posthog from "posthog-js";

import {
  type AnalyticsClient,
  NoopAnalytics,
} from "@/lib/analytics";

const KEY = process.env.NEXT_PUBLIC_POSTHOG_KEY;
const HOST = process.env.NEXT_PUBLIC_POSTHOG_HOST ?? "https://eu.i.posthog.com";


class PostHogAnalytics implements AnalyticsClient {
  private inited = false;

  init() {
    if (this.inited) return;
    if (typeof window === "undefined") return;
    if (!KEY) return;
    posthog.init(KEY, {
      api_host: HOST,
      // Respect user privacy — no session recording by default. Can be
      // toggled on per-page later if we want it for a specific flow.
      disable_session_recording: true,
      // Captures pageviews automatically via the SPA hook.
      capture_pageview: true,
      // We don't have email / login flows; PostHog's anonymous id is fine.
      persistence: "localStorage+cookie",
    });
    this.inited = true;
  }

  identify(distinctId: string, traits?: Record<string, unknown>) {
    if (!this.inited) return;
    posthog.identify(distinctId, traits);
  }

  track(event: string, props?: Record<string, unknown>) {
    if (!this.inited) return;
    posthog.capture(event, props);
  }

  reset() {
    if (!this.inited) return;
    posthog.reset();
  }
}


export const analytics: AnalyticsClient =
  KEY && typeof window !== "undefined" ? new PostHogAnalytics() : new NoopAnalytics();
