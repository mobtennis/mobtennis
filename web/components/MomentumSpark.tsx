/**
 * Tiny momentum sparkline — a teaser on match cards hinting that the full
 * Momentum Wave lives on the match page. Same visual language as the wave:
 * green above the centre line = player1 rising, blue below = player2.
 *
 * Presentational + tiny; the parent card is the click target.
 */

const A = "#16A34A"; // player1 — grass green
const B = "#2563EB"; // player2 — hard-court blue

export function MomentumSpark({
  spark,
  className,
}: {
  spark: number[];
  className?: string;
}) {
  if (!spark || spark.length < 2) return null;

  const W = 100;
  const H = 24;
  const pad = 2;
  const mid = H / 2;
  const n = spark.length;
  const x = (i: number) => (i / (n - 1)) * W;
  const y = (v: number) => mid - (Math.max(-100, Math.min(100, v)) / 100) * (mid - pad);

  // Smooth-ish path via midpoint quadratics — cheap and legible at small size.
  const pts = spark.map((v, i) => ({ x: x(i), y: y(v) }));
  let d = `M ${pts[0].x.toFixed(1)} ${pts[0].y.toFixed(1)}`;
  for (let i = 1; i < pts.length; i++) {
    const mx = (pts[i - 1].x + pts[i].x) / 2;
    const my = (pts[i - 1].y + pts[i].y) / 2;
    d += ` Q ${pts[i - 1].x.toFixed(1)} ${pts[i - 1].y.toFixed(1)} ${mx.toFixed(1)} ${my.toFixed(1)}`;
  }
  d += ` T ${pts[pts.length - 1].x.toFixed(1)} ${pts[pts.length - 1].y.toFixed(1)}`;

  const area = `${d} L ${W} ${mid} L 0 ${mid} Z`;
  const uid = `sp${spark.length}-${Math.round(spark[spark.length - 1])}`;

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      className={className}
      aria-hidden
      focusable="false"
    >
      <defs>
        {/* green up top, blue down low — reads as the wave leaning to whoever
            has momentum at that moment */}
        <linearGradient id={`${uid}-stroke`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={A} />
          <stop offset="50%" stopColor={A} />
          <stop offset="50%" stopColor={B} />
          <stop offset="100%" stopColor={B} />
        </linearGradient>
        <linearGradient id={`${uid}-fill`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={A} stopOpacity="0.18" />
          <stop offset="50%" stopColor={A} stopOpacity="0.04" />
          <stop offset="50%" stopColor={B} stopOpacity="0.04" />
          <stop offset="100%" stopColor={B} stopOpacity="0.18" />
        </linearGradient>
      </defs>
      {/* centre baseline */}
      <line x1="0" y1={mid} x2={W} y2={mid} stroke="currentColor" strokeOpacity="0.15" strokeWidth="0.5" />
      <path d={area} fill={`url(#${uid}-fill)`} stroke="none" />
      <path
        d={d}
        fill="none"
        stroke={`url(#${uid}-stroke)`}
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
