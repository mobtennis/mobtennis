import Link from "next/link";

/**
 * Landing page for shared round results. URL carries the score
 * details — set, score, max, pattern — so the OG metadata can
 * render a personalised unfurl card on social platforms.
 *
 *   /play/spot-the-ball/share?set=1&score=287&max=500&pattern=PCMPC
 *
 * Pattern encoding:
 *   P → perfect, C → close, M → miss (one char per puzzle in the
 *   round; same coding used by /api/og/spot-the-ball).
 *
 * Most visitors will be friends who tapped a shared link from
 * Twitter / Bluesky / Slack; the page nudges them toward the same
 * round so the comparison is meaningful.
 */

// Force-dynamic + no caching — every share URL is unique and we don't
// want Vercel collapsing them under the route cache.
export const dynamic = "force-dynamic";

type Search = {
  set?: string;
  score?: string;
  max?: string;
  pattern?: string;
};

function _ogImageUrl(s: Search): string {
  const params = new URLSearchParams({
    score: s.score ?? "0",
    max: s.max ?? "500",
    pattern: (s.pattern ?? "").toUpperCase(),
  });
  return `/api/og/spot-the-ball?${params.toString()}`;
}

export async function generateMetadata({
  searchParams,
}: {
  searchParams: Promise<Search>;
}) {
  const s = await searchParams;
  const score = s.score ?? "0";
  const max = s.max ?? "500";
  const title = `Spot the Ball · ${score}/${max}`;
  const description = `Played today's round on mob.tennis — scored ${score}/${max}. Can you beat it?`;
  const image = _ogImageUrl(s);
  return {
    title,
    description,
    openGraph: {
      title,
      description,
      images: [{ url: image, width: 1200, height: 630 }],
      type: "website",
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [image],
    },
  };
}

export default async function ShareLandingPage({
  searchParams,
}: {
  searchParams: Promise<Search>;
}) {
  const s = await searchParams;
  const score = Number(s.score ?? 0);
  const max = Number(s.max ?? 500);
  const pattern = (s.pattern ?? "").toUpperCase();
  const setHref =
    s.set && /^\d+$/.test(s.set)
      ? `/play/spot-the-ball/sets/${s.set}`
      : `/play/spot-the-ball`;

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <div className="text-[10px] font-bold uppercase tracking-wider text-accent">
          A friend shared their round
        </div>
        <h1 className="text-3xl font-bold tracking-tight">
          They scored {score}{" "}
          <span className="text-lg font-medium text-text-muted">/ {max}</span>
        </h1>
      </header>

      <PatternRow pattern={pattern} />

      <div className="rounded-lg border border-ink-700 bg-ink-900 p-5">
        <p className="text-sm text-text-secondary">
          Spot the Ball — 5 tennis action shots with the ball removed.
          One click each, cumulative score. Same 5 photos for everyone
          playing today.
        </p>
        <Link
          href={setHref}
          className="mt-4 inline-block rounded-md bg-accent px-4 py-3 text-sm font-bold uppercase tracking-wider text-white hover:bg-accent-dim"
        >
          Play this round →
        </Link>
      </div>
    </div>
  );
}


function PatternRow({ pattern }: { pattern: string }) {
  if (!pattern) return null;
  return (
    <div className="flex gap-2">
      {pattern.split("").map((c, i) => {
        const bg =
          c === "P"
            ? "bg-emerald-500"
            : c === "C"
              ? "bg-amber-500"
              : "bg-red-500";
        return <span key={i} className={`h-10 w-10 rounded ${bg}`} />;
      })}
    </div>
  );
}
