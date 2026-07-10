import { ImageResponse } from "next/og";

/**
 * Dynamic OG image for match pages.
 *
 *   /api/og/match?p1=Sinner&p2=Struff&score=6-4%206-3&status=live&event=Wimbledon%202026&round=QF
 *
 * A live match shares as a red LIVE badge + running score; a finished
 * one shows the final. 1200×630, edge runtime.
 */

export const runtime = "edge";

const BG_CREAM = "#FAF7F0";
const GRASS_GREEN = "#2F6E4B";
const INK_DARK = "#181E22";
const TEXT_MUTED = "#6F7872";
const LIVE_RED = "#C84746";

function clamp(s: string, n: number): string {
  return s.trim().slice(0, n);
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const p1 = clamp(searchParams.get("p1") ?? "—", 40);
  const p2 = clamp(searchParams.get("p2") ?? "—", 40);
  const score = clamp(searchParams.get("score") ?? "", 60);
  const status = (searchParams.get("status") ?? "").toLowerCase();
  const event = clamp(searchParams.get("event") ?? "", 60);
  const round = clamp(searchParams.get("round") ?? "", 30);
  const isLive = status === "live" || status === "suspended";
  const eyebrow = [event, round].filter(Boolean).join("  ·  ") || "Mob Tennis";

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
        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          {isLive && (
            <div
              style={{
                display: "flex",
                background: LIVE_RED,
                color: "#fff",
                fontSize: 24,
                fontWeight: 900,
                letterSpacing: "0.12em",
                padding: "6px 18px",
                borderRadius: 8,
              }}
            >
              LIVE
            </div>
          )}
          <div
            style={{
              display: "flex",
              fontSize: 28,
              color: GRASS_GREEN,
              fontWeight: 800,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
            }}
          >
            {eyebrow}
          </div>
        </div>

        <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center", gap: 18 }}>
          <div style={{ display: "flex", fontSize: 68, fontWeight: 800, color: INK_DARK, lineHeight: 1.05 }}>{p1}</div>
          <div style={{ display: "flex", fontSize: 40, color: TEXT_MUTED, fontWeight: 600 }}>vs</div>
          <div style={{ display: "flex", fontSize: 68, fontWeight: 800, color: INK_DARK, lineHeight: 1.05 }}>{p2}</div>
          {score && (
            <div style={{ display: "flex", marginTop: 12, fontSize: 46, fontWeight: 800, color: isLive ? LIVE_RED : GRASS_GREEN }}>
              {score}
            </div>
          )}
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
            {isLive ? "Follow live →" : "Match centre →"}
          </span>
        </div>
      </div>
    ),
    { width: 1200, height: 630 },
  );
}
