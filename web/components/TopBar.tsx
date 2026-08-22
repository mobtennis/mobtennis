import Link from "next/link";

export function TopBar() {
  return (
    <header className="sticky top-0 z-30 border-b border-ink-700 bg-ink-950/95 backdrop-blur">
      <div className="mx-auto flex h-12 max-w-3xl items-center justify-between px-4">
        {/* Left: logo + (desktop only) search icon */}
        <div className="flex items-center gap-3">
          <Link href="/" className="flex items-center gap-1.5">
            <Logo />
            <span className="font-bold tracking-tight">
              <span className="text-accent">mob</span>tennis
            </span>
          </Link>
          <Link
            href="/search"
            className="hidden text-text-secondary hover:text-text-primary md:block"
            aria-label="Search"
          >
            <SearchIcon />
          </Link>
        </div>

        {/* Right: desktop nav (md+), or search icon on mobile */}
        <nav className="hidden items-center gap-5 text-sm font-medium text-text-secondary md:flex">
          <Link href="/" className="hover:text-text-primary">Live</Link>
          <Link href="/tournaments" className="hover:text-text-primary">Tournaments</Link>
          <Link href="/rankings/atp" className="hover:text-text-primary">Rankings</Link>
          <Link href="/news" className="hover:text-text-primary">News</Link>
          <Link href="/following" className="text-accent hover:text-accent-dim">Get the app</Link>
        </nav>
        <Link
          href="/search"
          className="text-text-secondary hover:text-text-primary md:hidden"
          aria-label="Search"
        >
          <SearchIcon />
        </Link>
      </div>
    </header>
  );
}

function SearchIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="11" cy="11" r="7" />
      <path d="M21 21l-4.3-4.3" />
    </svg>
  );
}

function Logo() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" />
      <path d="M3.5 8.5C7 11 17 11 20.5 8.5M3.5 15.5C7 13 17 13 20.5 15.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}
