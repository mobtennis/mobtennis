/**
 * "Momentum building" placeholder — shown for a live match that hasn't yet
 * played enough games (≈4) for the momentum read to mean anything. An
 * equalizer of green/blue bars rising and falling, so the absence reads as
 * "warming up", not "missing".
 *
 * `size="mini"` fits the centre slot of a listing card; `size="panel"` is the
 * standalone card on the match page (with copy explaining the wait).
 */

const BARS = [
  { c: "#16A34A", d: "0ms" },
  { c: "#16A34A", d: "140ms" },
  { c: "#2563EB", d: "280ms" },
  { c: "#2563EB", d: "420ms" },
  { c: "#16A34A", d: "560ms" },
];

function Equalizer({ h }: { h: number }) {
  return (
    <span className="flex items-center gap-[2px]" style={{ height: h }} aria-hidden>
      {BARS.map((b, i) => (
        <span
          key={i}
          className="momentum-bar inline-block w-[3px] rounded-full"
          style={{ height: h, background: b.c, opacity: 0.7, animationDelay: b.d }}
        />
      ))}
    </span>
  );
}

export function MomentumBuilding({ size = "mini" }: { size?: "mini" | "panel" }) {
  if (size === "mini") {
    return (
      <span
        className="flex items-center"
        title="Momentum builds over the first few games"
      >
        <Equalizer h={16} />
      </span>
    );
  }
  return (
    <div className="flex items-center gap-3 rounded-lg border border-ink-700 bg-ink-900 px-4 py-3 shadow-card">
      <Equalizer h={22} />
      <div>
        <div className="text-sm font-semibold text-text-primary">Momentum building…</div>
        <div className="text-xs text-text-secondary">
          The wave needs the first few games to read the match — check back after a
          couple of holds and breaks.
        </div>
      </div>
    </div>
  );
}
