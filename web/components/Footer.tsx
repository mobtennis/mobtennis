import Link from "next/link";

export function Footer() {
  return (
    <footer className="mx-auto mt-8 max-w-3xl border-t border-ink-700/40 px-4 pt-6 pb-3 text-[11px] text-text-muted">
      <nav className="flex items-center justify-center gap-4">
        <Link
          href="/about"
          className="underline decoration-dotted underline-offset-2 hover:text-text-secondary"
        >
          About
        </Link>
        <span aria-hidden>·</span>
        <Link
          href="/credits"
          className="underline decoration-dotted underline-offset-2 hover:text-text-secondary"
        >
          Credits
        </Link>
      </nav>
    </footer>
  );
}
