type Props = {
  instagramHandle: string | null;
  twitterHandle: string | null;
  /** Latest post permalink — when present we render the Instagram embed iframe. */
  latestPostUrl: string | null;
  playerName: string;
};

export function SocialCard({ instagramHandle, twitterHandle, latestPostUrl, playerName }: Props) {
  if (!instagramHandle && !twitterHandle) return null;

  return (
    <section>
      <h2 className="px-1 text-base font-semibold tracking-tight">Social</h2>
      <div className="mt-2 space-y-2">
        {instagramHandle && (
          <a
            href={`https://www.instagram.com/${instagramHandle}/`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-3 rounded-md border border-ink-700 bg-ink-900 px-3 py-2.5 transition hover:border-accent"
          >
            <InstagramGlyph />
            <span className="min-w-0 flex-1 leading-tight">
              <span className="block text-sm font-semibold">Instagram</span>
              <span className="block truncate text-[11px] text-text-muted">@{instagramHandle}</span>
            </span>
            <ArrowIcon />
          </a>
        )}
        {twitterHandle && (
          <a
            href={`https://x.com/${twitterHandle}`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-3 rounded-md border border-ink-700 bg-ink-900 px-3 py-2.5 transition hover:border-accent"
          >
            <XGlyph />
            <span className="min-w-0 flex-1 leading-tight">
              <span className="block text-sm font-semibold">X</span>
              <span className="block truncate text-[11px] text-text-muted">@{twitterHandle}</span>
            </span>
            <ArrowIcon />
          </a>
        )}

        {latestPostUrl && (
          <div className="overflow-hidden rounded-md border border-ink-700 bg-ink-900">
            <iframe
              src={`${latestPostUrl.replace(/\/?$/, "/")}embed`}
              title={`Latest Instagram post from ${playerName}`}
              allow="encrypted-media"
              allowFullScreen
              loading="lazy"
              className="h-[640px] w-full"
            />
          </div>
        )}
      </div>
    </section>
  );
}

const stroke = {
  fill: "none" as const,
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

function InstagramGlyph() {
  return (
    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-gradient-to-br from-amber-400 via-rose-500 to-fuchsia-600 text-white">
      <svg width="18" height="18" viewBox="0 0 24 24" {...stroke} stroke="white">
        <rect x="3" y="3" width="18" height="18" rx="5" />
        <circle cx="12" cy="12" r="4" />
        <circle cx="17.5" cy="6.5" r="0.5" fill="white" stroke="none" />
      </svg>
    </span>
  );
}

function XGlyph() {
  return (
    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-text-primary text-white">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
        <path d="M18.244 2H21.5l-7.46 8.527L22.5 22h-6.815l-5.34-6.99L4.235 22H1l7.96-9.098L1.5 2h6.953l4.836 6.392L18.244 2zm-1.193 18h1.853L7.04 4h-1.97l11.98 16z" />
      </svg>
    </span>
  );
}

function ArrowIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="shrink-0 text-text-muted"
    >
      <path d="M7 17L17 7M9 7h8v8" />
    </svg>
  );
}
