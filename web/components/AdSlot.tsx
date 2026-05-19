/**
 * Network-agnostic ad slot. Two real networks supported (Ezoic + AdSense);
 * the rendered markup is whichever the configured network needs. Switching
 * is a config flip — no code change at the slot call sites.
 *
 * Render modes:
 *   "off"         — nothing
 *   "placeholder" — dashed-border preview (default in dev)
 *   "live"        — real ad markup for the configured network
 *
 * Network selection (one of):
 *   NEXT_PUBLIC_AD_NETWORK      = "adsense" | "ezoic" | "off"
 *   ↳ When unset, falls back to "adsense" iff NEXT_PUBLIC_ADSENSE_CLIENT_ID
 *     is set (legacy behaviour), else "off" in prod / "placeholder" in dev.
 *
 * Mode override (rare):
 *   NEXT_PUBLIC_ADS_MODE        = "off" | "placeholder" | "live"
 *
 * Per-slot unit IDs:
 *   NEXT_PUBLIC_ADSENSE_SLOT_*  — AdSense ad-unit ID per slot (existing).
 *   NEXT_PUBLIC_EZOIC_SLOT_*    — Ezoic numeric placeholder ID per slot.
 *
 * Ezoic discovers placeholders by ID. Their dashboard generates numbers
 * like 101, 102, … which you paste into env vars below. The Ezoic
 * loader script (sa.min.js) is mounted in layout.tsx when network=ezoic.
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
// deployments); else "off". Ezoic is opt-in only via the explicit env var.
const AD_NETWORK: "adsense" | "ezoic" | "off" =
  (process.env.NEXT_PUBLIC_AD_NETWORK as "adsense" | "ezoic" | "off" | undefined) ??
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

const EZOIC_SLOT_TO_PLACEHOLDER: Record<string, string | undefined> = {
  "home-mid":               process.env.NEXT_PUBLIC_EZOIC_SLOT_HOME_MID,
  "news-mid":               process.env.NEXT_PUBLIC_EZOIC_SLOT_NEWS_MID,
  "player-mid":             process.env.NEXT_PUBLIC_EZOIC_SLOT_PLAYER_MID,
  "tournament-mid":         process.env.NEXT_PUBLIC_EZOIC_SLOT_TOURNAMENT_MID,
  "match-mid":              process.env.NEXT_PUBLIC_EZOIC_SLOT_MATCH_MID,
  "rankings-mid":           process.env.NEXT_PUBLIC_EZOIC_SLOT_RANKINGS_MID,
  "tournaments-index-top":  process.env.NEXT_PUBLIC_EZOIC_SLOT_TOURNAMENTS_INDEX_TOP,
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
  if (AD_NETWORK === "ezoic") {
    const placeholderId = EZOIC_SLOT_TO_PLACEHOLDER[slot];
    if (!placeholderId) return null;
    // Ezoic discovers ad units by the numeric id on the div. Their
    // sa.min.js (mounted in layout.tsx) handles the rest — bidding,
    // placement, refresh — based on the placeholder dashboard config.
    return (
      <div
        id={`ezoic-pub-ad-placeholder-${placeholderId}`}
        data-ad-slot={slot}
        className={`w-full ${MIN_HEIGHTS[size]}`}
      />
    );
  }

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
