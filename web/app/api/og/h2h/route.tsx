import { ImageResponse } from "next/og";

/**
 * Dynamic OG image for head-to-head pages.
 *
 *   /api/og/h2h?p1=Carlos%20Alcaraz&p2=Jannik%20Sinner&w1=4&w2=6
 *
 * 1200×630, edge runtime — same contract as the Spot the Ball card so
 * every unfurler (X, WhatsApp, Slack, Discord, iMessage) renders it.
 */

export const runtime = "edge";

const BG_CREAM = "#FAF7F0";
const GRASS_GREEN = "#2F6E4B";
const INK_DARK = "#181E22";
const TEXT_MUTED = "#6F7872";
const ACCENT = "#2E9D5C";

function clampName(s: string): string {
  const t = s.trim().slice(0, 40);
  return t || "—";
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const p1 = clampName(searchParams.get("p1") ?? "");
  const p2 = clampName(searchParams.get("p2") ?? "");
  const w1 = (searchParams.get("w1") ?? "0").replace(/[^0-9]/g, "").slice(0, 3) || "0";
  const w2 = (searchParams.get("w2") ?? "0").replace(/[^0-9]/g, "").slice(0, 3) || "0";

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          background: BG_CREAM,
          padding: "70px 80px",
          fontFamily: "system-ui, -apple-system, sans-serif",
        }}
      >
        <div
          style={{
            display: "flex",
            fontSize: 28,
            color: GRASS_GREEN,
            fontWeight: 800,
            letterSpacing: "0.15em",
            textTransform: "uppercase",
          }}
        >
          🎾  Head-to-Head
        </div>

        <div
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 30,
          }}
        >
          <div style={{ display: "flex", width: 380, fontSize: 56, fontWeight: 800, color: INK_DARK, lineHeight: 1.1 }}>
            {p1}
          </div>
          <div style={{ display: "flex", alignItems: "baseline", color: ACCENT, fontWeight: 900 }}>
            <span style={{ fontSize: 140, lineHeight: 1 }}>{w1}</span>
            <span style={{ fontSize: 80, color: TEXT_MUTED, margin: "0 18px" }}>–</span>
            <span style={{ fontSize: 140, lineHeight: 1 }}>{w2}</span>
          </div>
          <div style={{ display: "flex", width: 380, justifyContent: "flex-end", textAlign: "right", fontSize: 56, fontWeight: 800, color: INK_DARK, lineHeight: 1.1 }}>
            {p2}
          </div>
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            color: GRASS_GREEN,
            fontSize: 36,
            fontWeight: 800,
          }}
        >
          <span>mob.tennis</span>
          <span style={{ fontSize: 24, color: TEXT_MUTED, fontWeight: 500 }}>
            Full rivalry →
          </span>
        </div>
      </div>
    ),
    { width: 1200, height: 630 },
  );
}
