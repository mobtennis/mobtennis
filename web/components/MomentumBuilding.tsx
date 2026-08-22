/**
 * "Momentum building" placeholder — shown for a live match that hasn't yet
 * played enough games (≈4) for the momentum read to mean anything, so the
 * absence reads as "warming up", not "missing".
 *
 * `size="mini"` (listing cards) is a single throbbing dot with a tooltip.
 * `size="panel"` (match page) is an undulating wave echoing the real
 * Momentum Wave, plus copy explaining the wait.
 */

const A = "#16A34A"; // player1 — grass green
const B = "#2563EB"; // player2 — hard-court blue

// A smooth sine path holding TWO identical periods across the viewBox, so a
// -50% horizontal scroll loops seamlessly (see .momentum-wave-scroll).
function wavePath(): { line: string; area: string } {
  const W = 240;
  const H = 40;
  const mid = H / 2;
  const amp = 9;
  const period = W / 2; // two full periods across the width
  const pts: [number, number][] = [];
  for (let x = 0; x <= W; x += 4) {
    pts.push([x, mid - amp * Math.sin((2 * Math.PI * x) / period)]);
  }
  const line = pts.map(([x, y], i) => `${i ? "L" : "M"} ${x} ${y.toFixed(1)}`).join(" ");
  const area = `${line} L ${W} ${H} L 0 ${H} Z`;
  return { line, area };
}

function BuildingWave() {
  const { line, area } = wavePath();
  return (
    <div className="relative h-10 flex-1 overflow-hidden rounded-md">
      <svg
        viewBox="0 0 240 40"
        preserveAspectRatio="none"
        className="momentum-wave-scroll block h-full"
        aria-hidden
        focusable="false"
      >
        <defs>
          <linearGradient id="mbw-stroke" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={A} />
            <stop offset="50%" stopColor={A} />
            <stop offset="50%" stopColor={B} />
            <stop offset="100%" stopColor={B} />
          </linearGradient>
          <linearGradient id="mbw-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={A} stopOpacity="0.16" />
            <stop offset="100%" stopColor={A} stopOpacity="0.02" />
          </linearGradient>
        </defs>
        <path d={area} fill="url(#mbw-fill)" />
        <path
          d={line}
          fill="none"
          stroke="url(#mbw-stroke)"
          strokeWidth="1.5"
          strokeLinejoin="round"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
          opacity="0.6"
        />
      </svg>
    </div>
  );
}

export function MomentumBuilding({ size = "mini" }: { size?: "mini" | "panel" }) {
  if (size === "mini") {
    // A single throbbing dot in the card's centre slot — the tooltip carries
    // the explanation; a fuller animation is too busy in a dense list.
    return (
      <span
        className="flex items-center justify-center"
        title="Momentum builds over the first few games"
      >
        <span className="momentum-dot inline-block h-2 w-2 rounded-full bg-text-muted" />
      </span>
    );
  }
  return (
    <section>
      <div className="mb-1 text-base font-semibold tracking-tight">Momentum</div>
      <div className="flex items-center gap-4 rounded-lg border border-ink-700 bg-ink-900 px-4 py-3 shadow-card">
        <BuildingWave />
        <div className="shrink-0 basis-1/2">
          <div className="text-sm font-semibold text-text-primary">Momentum building…</div>
          <div className="text-xs text-text-secondary">
            The wave needs the first few games to read the match — check back after a
            couple of holds and breaks.
          </div>
        </div>
      </div>
    </section>
  );
}
