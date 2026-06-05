import { ImageResponse } from "next/og";

/**
 * Dynamic OG image for shareable Spot the Ball results.
 *
 *   /api/og/spot-the-ball?score=287&max=500&pattern=PCMPC
 *
 * Pattern is a compact string of band letters per round image:
 *   P → perfect (green square)
 *   C → close   (amber square)
 *   M → miss    (red square)
 *
 * 1200×630 — standard Open Graph dimensions accepted by every
 * unfurler. Edge runtime so social-card crawlers don't time out
 * on cold-starts.
 */

export const runtime = "edge";

// Light-and-sunny palette per the visual-design memory.
const BG_CREAM = "#FAF7F0";
const GRASS_GREEN = "#2F6E4B";
const INK_DARK = "#181E22";
const TEXT_MUTED = "#6F7872";
const PERFECT_GREEN = "#2E9D5C";
const CLOSE_AMBER = "#D9A52A";
const MISS_RED = "#C84746";

function colorFor(c: string): string {
  if (c === "P") return PERFECT_GREEN;
  if (c === "C") return CLOSE_AMBER;
  if (c === "M") return MISS_RED;
  return "#888";
}


export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const score = searchParams.get("score") ?? "0";
  const max = searchParams.get("max") ?? "500";
  const patternRaw = (searchParams.get("pattern") ?? "").toUpperCase();
  // Clamp to a sane length so a malformed query can't blow out
  // the canvas.
  const pattern = patternRaw.slice(0, 10).split("");

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
        {/* Eyebrow */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 14,
            fontSize: 28,
            color: GRASS_GREEN,
            fontWeight: 800,
            letterSpacing: "0.15em",
            textTransform: "uppercase",
          }}
        >
          🎾  Spot the Ball
        </div>

        {/* Big score block */}
        <div
          style={{
            marginTop: 50,
            display: "flex",
            alignItems: "baseline",
            color: INK_DARK,
          }}
        >
          <span style={{ fontSize: 220, fontWeight: 900, lineHeight: 1, letterSpacing: "-0.04em" }}>
            {score}
          </span>
          <span
            style={{
              fontSize: 64,
              fontWeight: 500,
              color: TEXT_MUTED,
              marginLeft: 24,
            }}
          >
            / {max}
          </span>
        </div>

        {/* Emoji-square pattern */}
        <div style={{ marginTop: 40, display: "flex", gap: 18 }}>
          {pattern.map((c, i) => (
            <div
              key={i}
              style={{
                width: 90,
                height: 90,
                borderRadius: 14,
                background: colorFor(c),
              }}
            />
          ))}
        </div>

        {/* Spacer pushes the URL to the bottom */}
        <div style={{ flex: 1 }} />

        {/* Brand line */}
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
            Play your round →
          </span>
        </div>
      </div>
    ),
    { width: 1200, height: 630 },
  );
}
