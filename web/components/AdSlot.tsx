/**
 * Single ad slot. Three render modes:
 *
 *   "off"         — renders nothing (default in prod when no client ID configured)
 *   "placeholder" — dashed-border preview (default in dev)
 *   "live"        — real AdSense <ins> + a one-shot adsbygoogle.push() call
 *
 * Mode selection:
 *   NEXT_PUBLIC_ADS_MODE   — explicit override ("off" / "placeholder" / "live")
 *   NEXT_PUBLIC_ADSENSE_CLIENT_ID — when set + mode unset, defaults to "live"
 *
 * Per-slot AdSense unit IDs come from env vars (see SLOT_TO_UNIT_ID below).
 * If the unit ID for a given slot is missing, the slot renders nothing rather
 * than serving a broken ad — easier to diagnose than a malformed unit.
 */

import { AdSenseInit } from "@/components/AdSenseInit";

type Props = {
  slot: string;
  /** Approximate banner shape. Affects min-height only — width fills container. */
  size?: "rectangle" | "leaderboard" | "responsive";
};

const MIN_HEIGHTS: Record<NonNullable<Props["size"]>, string> = {
  rectangle: "min-h-[100px]",     // ~mobile banner / inline rectangle
  leaderboard: "min-h-[90px]",    // 728x90 desktop leaderboard
  responsive: "min-h-[120px]",    // tall enough for 300x250 medium-rectangle
};

const AD_CLIENT_ID = process.env.NEXT_PUBLIC_ADSENSE_CLIENT_ID;

const ADS_MODE: "off" | "placeholder" | "live" =
  (process.env.NEXT_PUBLIC_ADS_MODE as "off" | "placeholder" | "live" | undefined) ??
  (AD_CLIENT_ID
    ? "live"
    : process.env.NODE_ENV === "development"
      ? "placeholder"
      : "off");

// Maps our internal slot identifier → the AdSense ad-unit ID configured in
// the AdSense dashboard. Each is set via env var so we don't redeploy on
// dashboard changes.
const SLOT_TO_UNIT_ID: Record<string, string | undefined> = {
  "home-mid":               process.env.NEXT_PUBLIC_ADSENSE_SLOT_HOME_MID,
  "news-mid":               process.env.NEXT_PUBLIC_ADSENSE_SLOT_NEWS_MID,
  "player-mid":             process.env.NEXT_PUBLIC_ADSENSE_SLOT_PLAYER_MID,
  "tournament-mid":         process.env.NEXT_PUBLIC_ADSENSE_SLOT_TOURNAMENT_MID,
  "match-mid":              process.env.NEXT_PUBLIC_ADSENSE_SLOT_MATCH_MID,
  "rankings-mid":           process.env.NEXT_PUBLIC_ADSENSE_SLOT_RANKINGS_MID,
  "tournaments-index-top":  process.env.NEXT_PUBLIC_ADSENSE_SLOT_TOURNAMENTS_INDEX_TOP,
};

export function AdSlot({ slot, size = "rectangle" }: Props) {
  if (ADS_MODE === "off") return null;

  if (ADS_MODE === "placeholder") {
    return (
      <aside
        role="complementary"
        aria-label={`Ad slot: ${slot}`}
        data-ad-slot={slot}
        className={`flex w-full items-center justify-center rounded-lg border border-dashed border-ink-700 bg-ink-900/40 px-3 py-4 ${MIN_HEIGHTS[size]}`}
      >
        <div className="text-center">
          <div className="text-[10px] font-bold uppercase tracking-wider text-text-muted">
            Sponsored
          </div>
          <div className="mt-1 text-[11px] text-text-muted/70">Ad placeholder · {slot}</div>
        </div>
      </aside>
    );
  }

  // ADS_MODE === "live"
  const unitId = SLOT_TO_UNIT_ID[slot];
  if (!AD_CLIENT_ID || !unitId) return null;

  return (
    <>
      <ins
        className="adsbygoogle block"
        style={{ display: "block" }}
        data-ad-client={AD_CLIENT_ID}
        data-ad-slot={unitId}
        data-ad-format="auto"
        data-full-width-responsive="true"
      />
      <AdSenseInit />
    </>
  );
}
