import Link from "next/link";

import {
  api,
  type CallTheShotSet,
  type NameTheProSet,
  type SpotTheBallSet,
} from "@/lib/api";

export const revalidate = 300;

export const metadata = {
  title: "Play",
  description: "Daily tennis games — Spot the Ball and Name the Pro.",
};

type GameCard = {
  href: string;
  title: string;
  tagline: string;
  description: string;
  cover_image_url: string | null;
  publish_date: string | null;
  image_count: number | null;
  pill: string;
};

export default async function PlayHubPage() {
  const [stb, ntp, cts] = await Promise.all([
    api<SpotTheBallSet>("/api/spot-the-ball/today", { revalidate: 300 }).catch(
      () => null,
    ),
    api<NameTheProSet>("/api/name-the-pro/today", { revalidate: 300 }).catch(
      () => null,
    ),
    api<CallTheShotSet>("/api/call-the-shot/today", { revalidate: 300 }).catch(
      () => null,
    ),
  ]);

  const cards: GameCard[] = [
    {
      href: "/play/spot-the-ball",
      title: "Spot the ball",
      tagline: "Click where the ball was",
      description:
        "Five tennis action shots with the ball removed. Closer click, more points. Daily round.",
      cover_image_url: stb?.images?.[0]?.image_url ?? null,
      publish_date: stb?.publish_date ?? null,
      image_count: stb?.images?.length ?? null,
      pill: "Today's round",
    },
    {
      href: "/play/name-the-pro",
      title: "Name the pro",
      tagline: "Four guesses per photo",
      description:
        "Five photos of pros from across the rankings. One headliner, four deeper picks. Multiple choice.",
      cover_image_url: ntp?.images?.[0]?.image_url ?? null,
      publish_date: ntp?.publish_date ?? null,
      image_count: ntp?.images?.length ?? null,
      pill: "New",
    },
    {
      href: "/play/call-the-shot",
      title: "Call the shot",
      tagline: "Predict where the ball is going",
      description:
        "Highlight clip pauses mid-rally. Pick where the next shot is going, video plays the resolution.",
      cover_image_url: null,
      publish_date: cts?.publish_date ?? null,
      image_count: cts?.items?.length ?? null,
      pill: cts ? "Today's round" : "New",
    },
  ];

  return (
    <div className="space-y-8">
      <header className="space-y-2">
        <div className="text-[10px] font-bold uppercase tracking-wider text-accent">
          Daily games
        </div>
        <h1 className="text-3xl font-bold tracking-tight">Play</h1>
        <p className="max-w-prose text-sm text-text-secondary">
          Three short rounds, refreshed daily. No login, no streaks — just
          tennis. Share your score when you're done.
        </p>
      </header>

      <ul className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {cards.map((c) => (
          <li
            key={c.href}
            className="overflow-hidden rounded-lg border border-ink-700 bg-ink-900 shadow-card"
          >
            <Link href={c.href} className="group block">
              <div className="relative aspect-video w-full overflow-hidden bg-ink-950">
                {c.cover_image_url ? (
                  /* eslint-disable-next-line @next/next/no-img-element */
                  <img
                    src={c.cover_image_url}
                    alt={c.title}
                    className="h-full w-full object-cover transition-opacity group-hover:opacity-90"
                    loading="lazy"
                  />
                ) : (
                  <div className="flex h-full w-full items-center justify-center text-xs uppercase tracking-wider text-text-muted">
                    No round yet
                  </div>
                )}
                <span className="absolute left-3 top-3 rounded-full bg-accent px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-white shadow-lg">
                  {c.pill}
                </span>
              </div>
              <div className="space-y-2 p-4">
                <div className="text-[10px] uppercase tracking-wider text-text-muted">
                  {c.publish_date
                    ? `${c.publish_date}${c.image_count ? ` · ${c.image_count} images` : ""}`
                    : "Round coming soon"}
                </div>
                <div>
                  <div className="text-lg font-bold text-text-primary">
                    {c.title}
                  </div>
                  <div className="text-sm font-medium text-accent">
                    {c.tagline}
                  </div>
                </div>
                <p className="text-sm text-text-secondary">{c.description}</p>
              </div>
            </Link>
          </li>
        ))}
      </ul>

      <div className="flex flex-wrap gap-4 text-sm">
        <Link
          href="/play/spot-the-ball/archive"
          className="font-medium text-accent hover:text-accent-dim"
        >
          Spot the ball archive →
        </Link>
        <Link
          href="/play/name-the-pro/archive"
          className="font-medium text-accent hover:text-accent-dim"
        >
          Name the pro archive →
        </Link>
        <Link
          href="/play/call-the-shot/archive"
          className="font-medium text-accent hover:text-accent-dim"
        >
          Call the shot archive →
        </Link>
      </div>
    </div>
  );
}
