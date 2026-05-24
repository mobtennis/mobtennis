type Props = {
  /** What the user was about to personalize, e.g. "follow Carlos Alcaraz". */
  action?: string;
  variant?: "card" | "inline";
  className?: string;
};

// Placeholder app links — wire to real store URLs once apps ship.
const IOS_URL = "/app/ios";
const ANDROID_URL = "/app/android";

export function GetTheAppCard({ action, variant = "card", className }: Props) {
  if (variant === "inline") {
    return (
      <a
        href={IOS_URL}
        className={`inline-flex items-center gap-1.5 rounded-full border border-ink-700 bg-ink-900 px-3 py-1 text-xs font-semibold text-text-secondary hover:border-accent hover:text-accent ${className ?? ""}`}
      >
        <PhoneIcon />
        Get the app to {action ?? "personalize"}
      </a>
    );
  }
  return (
    <section className={`rounded-lg border border-ink-700 bg-gradient-to-br from-ink-800 to-ink-900 p-5 shadow-card ${className ?? ""}`}>
      <div className="flex items-start gap-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent/15 text-accent">
          <PhoneIcon size={22} />
        </div>
        <div className="flex-1">
          <h3 className="text-base font-semibold tracking-tight">
            {action ? `${capitalize(action)} in the app` : "Personalize Mob Tennis in the app"}
          </h3>
          <p className="mt-1 text-sm text-text-secondary">
            Follow your favourite players and tournaments, get score alerts, and take Mob Tennis with
            you to the court. No account needed — your follows live on your phone.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <StoreBadge href={IOS_URL} label="App Store" sub="iPhone & iPad" />
            <StoreBadge href={ANDROID_URL} label="Google Play" sub="Android" />
          </div>
        </div>
      </div>
    </section>
  );
}

function StoreBadge({ href, label, sub }: { href: string; label: string; sub: string }) {
  return (
    <a
      href={href}
      className="inline-flex items-center gap-2 rounded-md border border-ink-700 bg-ink-950 px-3 py-2 text-left transition hover:border-accent"
    >
      <span className="flex h-7 w-7 items-center justify-center rounded bg-accent text-ink-950">
        <DownloadIcon />
      </span>
      <span className="leading-tight">
        <span className="block text-[10px] uppercase tracking-wider text-text-muted">{sub}</span>
        <span className="block text-sm font-semibold">{label}</span>
      </span>
    </a>
  );
}

function PhoneIcon({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="6" y="2" width="12" height="20" rx="2" />
      <path d="M11 18h2" />
    </svg>
  );
}

function DownloadIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3v12m-5-5l5 5 5-5M5 21h14" />
    </svg>
  );
}

function capitalize(s: string) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
