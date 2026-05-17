import type { Tour } from "@/lib/api";

type Props = {
  name: string;
  tour: Tour;
};

// Search-based deep links — robust to player name disambiguation without
// needing the official ATP/WTA numeric IDs (which we don't have).
export function ExternalLinks({ name, tour }: Props) {
  const q = encodeURIComponent(name);

  const wikiUrl = `https://en.wikipedia.org/wiki/Special:Search?go=Go&search=${encodeURIComponent(`${name} tennis`)}`;
  const tourUrl =
    tour === "atp"
      ? `https://www.atptour.com/en/players?search=${q}`
      : `https://www.wtatennis.com/search?q=${q}`;
  const tourLabel = tour === "atp" ? "ATP Tour" : "WTA";
  const ytUrl = `https://www.youtube.com/results?search_query=${encodeURIComponent(`${name} highlights`)}`;

  return (
    <section>
      <h2 className="px-1 text-base font-semibold tracking-tight">Find out more</h2>
      <ul className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
        <ExternalLink href={tourUrl} title={tourLabel} subtitle="Official profile" icon={<TrophyIcon />} />
        <ExternalLink href={wikiUrl} title="Wikipedia" subtitle="Career & bio" icon={<WikiIcon />} />
        <ExternalLink href={ytUrl} title="YouTube" subtitle="Highlights" icon={<PlayIcon />} />
      </ul>
    </section>
  );
}

function ExternalLink({
  href,
  title,
  subtitle,
  icon,
}: {
  href: string;
  title: string;
  subtitle: string;
  icon: React.ReactNode;
}) {
  return (
    <li>
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center gap-2.5 rounded-md border border-ink-700 bg-ink-900 px-3 py-2.5 transition hover:border-accent hover:bg-ink-800"
      >
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-ink-700 text-text-secondary">
          {icon}
        </span>
        <span className="min-w-0 flex-1 leading-tight">
          <span className="block text-sm font-semibold">{title}</span>
          <span className="block truncate text-[11px] text-text-muted">{subtitle}</span>
        </span>
        <span className="shrink-0 text-text-muted">
          <ArrowIcon />
        </span>
      </a>
    </li>
  );
}

const stroke = {
  fill: "none" as const,
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

function TrophyIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" {...stroke}>
      <path d="M7 4h10v3a5 5 0 1 1-10 0V4z" />
      <path d="M7 6H4a3 3 0 0 0 3 3M17 6h3a3 3 0 0 1-3 3" />
      <path d="M9 14h6l-1 5h-4l-1-5z" />
      <path d="M8 21h8" />
    </svg>
  );
}
function WikiIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" {...stroke}>
      <path d="M2 6l5 14 5-12 5 12 5-14" />
    </svg>
  );
}
function PlayIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" {...stroke}>
      <path d="M5 4l14 8-14 8V4z" fill="currentColor" />
    </svg>
  );
}
function ArrowIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" {...stroke}>
      <path d="M7 17L17 7M9 7h8v8" />
    </svg>
  );
}
