import { ImageResponse } from "next/og";

/**
 * Dynamic OG image for player pages.
 *
 *   /api/og/player?name=Jannik%20Sinner&rank=1&tour=atp&country=ITA
 *
 * 1200×630, edge runtime.
 */

export const runtime = "edge";

const BG_CREAM = "#FAF7F0";
const GRASS_GREEN = "#2F6E4B";
const INK_DARK = "#181E22";
const TEXT_MUTED = "#6F7872";

function clamp(s: string, n: number): string {
  return s.trim().slice(0, n);
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const name = clamp(searchParams.get("name") ?? "—", 44);
  const tour = (searchParams.get("tour") ?? "").toUpperCase().replace(/[^A-Z]/g, "").slice(0, 4);
  const rank = (searchParams.get("rank") ?? "").replace(/[^0-9]/g, "").slice(0, 4);
  const country = clamp(searchParams.get("country") ?? "", 3).toUpperCase();
  const rankLine = rank ? `${tour || "Current"} #${rank}` : (tour ? `${tour} Tour` : "");

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
          🎾  Player Profile
        </div>

        <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center" }}>
          <div style={{ display: "flex", fontSize: 96, fontWeight: 900, color: INK_DARK, lineHeight: 1.05, letterSpacing: "-0.02em" }}>
            {name}
          </div>
          {(rankLine || country) && (
            <div style={{ display: "flex", alignItems: "center", gap: 24, marginTop: 24 }}>
              {rankLine && (
                <div style={{ display: "flex", fontSize: 44, fontWeight: 800, color: GRASS_GREEN }}>{rankLine}</div>
              )}
              {country && (
                <div style={{ display: "flex", fontSize: 36, fontWeight: 600, color: TEXT_MUTED }}>{country}</div>
              )}
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
            Profile, form &amp; H2H →
          </span>
        </div>
      </div>
    ),
    { width: 1200, height: 630 },
  );
}
