/**
 * Network-agnostic ad slot. AdSense is the only supported live
 * network; the structure remains "network-agnostic" so swapping in
 * another network later is a contained change.
 *
 * Render modes:
 *   "off"         — nothing
 *   "placeholder" — dashed-border preview (default in dev)
 *   "live"        — real ad markup for the configured network
 *
 * Network selection:
 *   NEXT_PUBLIC_AD_NETWORK      = "adsense" | "off"
 *   ↳ When unset, falls back to "adsense" iff NEXT_PUBLIC_ADSENSE_CLIENT_ID
 *     is set (legacy behaviour), else "off" in prod / "placeholder" in dev.
 *
 * Mode override (rare):
 *   NEXT_PUBLIC_ADS_MODE        = "off" | "placeholder" | "live"
 *
 * Per-slot unit IDs:
 *   NEXT_PUBLIC_ADSENSE_SLOT_*  — AdSense ad-unit ID per slot.
 */

import { AdSenseInit } from "@/components/AdSenseInit";

type Props = {
  slot: string;
  /** Approximate banner shape. Affects min-height only — width fills container. */
  size?: "rectangle" | "leaderboard" | "responsive";
};

const MIN_HEIGHTS: Record<NonNullable<Props["size"]>, string> = {
  rectangle: "min-h-[100px]",
  leaderboard: "min-h-[90px]",
  responsive: "min-h-[120px]",
};

const AD_CLIENT_ID = process.env.NEXT_PUBLIC_ADSENSE_CLIENT_ID;

// Inferred default network: explicit override wins; else AdSense iff its
// client ID is configured (preserves the old behaviour for existing
// deployments); else "off".
const AD_NETWORK: "adsense" | "off" =
  (process.env.NEXT_PUBLIC_AD_NETWORK as "adsense" | "off" | undefined) ??
  (AD_CLIENT_ID ? "adsense" : "off");

const ADS_MODE: "off" | "placeholder" | "live" =
  (process.env.NEXT_PUBLIC_ADS_MODE as "off" | "placeholder" | "live" | undefined) ??
  (AD_NETWORK !== "off"
    ? "live"
    : process.env.NODE_ENV === "development"
      ? "placeholder"
      : "off");

const ADSENSE_SLOT_TO_UNIT: Record<string, string | undefined> = {
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
          <div className="mt-1 text-[11px] text-text-muted/70">
            Ad placeholder · {slot} · {AD_NETWORK}
          </div>
        </div>
      </aside>
    );
  }

  // ADS_MODE === "live"
  if (AD_NETWORK === "adsense") {
    const unitId = ADSENSE_SLOT_TO_UNIT[slot];
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

  return null;
}
