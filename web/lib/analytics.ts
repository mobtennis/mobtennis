/**
 * Analytics shape — implemented by the concrete client in
 * analytics-client.ts. Keeping the interface in its own module means
 * server components and pure helpers can import the EVENTS constant
 * without dragging the PostHog SDK into the server bundle.
 *
 * Swap-out plan: replacing PostHog with Plausible / Mixpanel / Amplitude
 * is one file (analytics-client.ts), no call-site changes needed.
 */

export interface AnalyticsClient {
  /** Idempotent — safe to call multiple times. */
  init(): void;
  /** Tag subsequent events with a stable user id (we use the device token). */
  identify(distinctId: string, traits?: Record<string, unknown>): void;
  /** Fire one event. */
  track(event: string, props?: Record<string, unknown>): void;
  /** Drop session, anonymise. Use on logout or device reset. */
  reset(): void;
}


/** Single source of truth for event names. Stops "filterToggled" vs
 *  "filter_toggled" drift across the codebase, and gives PostHog one
 *  clean list to filter dashboards against. */
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


/** Default no-op client. Used when no API key is configured so dev /
 *  preview environments don't pollute the prod project. */
export class NoopAnalytics implements AnalyticsClient {
  init() { /* no-op */ }
  identify() { /* no-op */ }
  track() { /* no-op */ }
  reset() { /* no-op */ }
}
