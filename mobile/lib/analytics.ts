/**
 * Mobile analytics — a thin HTTP wrapper for PostHog's `/capture/`
 * endpoint. We avoid the official `posthog-react-native` SDK because
 * it brings 5+ Expo peer dependencies that we'd otherwise not need;
 * for our event volume a direct fetch is simpler and works in Expo Go.
 *
 * Same shape as web/lib/analytics + web/lib/analytics-client so call
 * sites stay symmetrical. Replace the implementation with a different
 * provider by swapping this single file.
 */

import { getDeviceToken } from "@/lib/device";

const KEY = process.env.EXPO_PUBLIC_POSTHOG_KEY;
const HOST =
  process.env.EXPO_PUBLIC_POSTHOG_HOST ?? "https://eu.i.posthog.com";


/** Single source of truth for event names. Stops "filterToggled" vs
 *  "filter_toggled" drift across the codebase. */
export const EVENTS = {
  matchOpened: "match_opened",
  tournamentOpened: "tournament_opened",
  playerOpened: "player_opened",
  bracketShown: "bracket_shown",
  followToggled: "follow_toggled",
  matchAlertSubscribed: "match_alert_subscribed",
  filterToggled: "filter_toggled",
  searchPerformed: "search_performed",
  newsClicked: "news_clicked",
  pushPermission: "push_permission",
} as const;

export type EventName = (typeof EVENTS)[keyof typeof EVENTS];


export interface AnalyticsClient {
  init(): Promise<void> | void;
  identify(distinctId: string, traits?: Record<string, unknown>): void;
  track(event: string, props?: Record<string, unknown>): void;
  reset(): void;
}


class NoopAnalytics implements AnalyticsClient {
  init() { /* no-op */ }
  identify() { /* no-op */ }
  track() { /* no-op */ }
  reset() { /* no-op */ }
}


class PostHogAnalytics implements AnalyticsClient {
  private distinctId: string | null = null;
  private queue: { event: string; properties: Record<string, unknown> }[] = [];

  async init() {
    if (this.distinctId) return;
    try {
      // The device token doubles as our analytics identity — anonymous,
      // stable across launches, no PII attached.
      this.distinctId = await getDeviceToken();
    } catch {
      // SecureStore unavailable (rare). Fall back to a random per-session id
      // so events still attribute to *something*.
      this.distinctId = `anon-${Math.random().toString(36).slice(2, 10)}`;
    }
    // Drain any events queued before init resolved.
    const pending = this.queue;
    this.queue = [];
    for (const item of pending) this._send(item.event, item.properties);
  }

  identify(distinctId: string, traits?: Record<string, unknown>) {
    this.distinctId = distinctId;
    // PostHog identify is implemented via a `$set` capture event.
    this._send("$identify", {
      distinct_id: distinctId,
      $set: traits ?? {},
    });
  }

  track(event: string, props?: Record<string, unknown>) {
    const payload = props ?? {};
    if (!this.distinctId) {
      this.queue.push({ event, properties: payload });
      return;
    }
    this._send(event, payload);
  }

  reset() {
    this.distinctId = null;
    this.queue = [];
  }

  private _send(event: string, properties: Record<string, unknown>) {
    if (!KEY || !this.distinctId) return;
    const body = JSON.stringify({
      api_key: KEY,
      event,
      distinct_id: this.distinctId,
      properties,
      timestamp: new Date().toISOString(),
    });
    // Fire-and-forget. Failures are intentionally silent — analytics
    // must never break the app. PostHog's capture endpoint is fast and
    // resilient; we don't bother with retries or batching at our scale.
    fetch(`${HOST.replace(/\/$/, "")}/capture/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    }).catch(() => {
      /* swallow */
    });
  }
}


export const analytics: AnalyticsClient = KEY
  ? new PostHogAnalytics()
  : new NoopAnalytics();
