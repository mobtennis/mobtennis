import Link from "next/link";

export function Footer() {
  return (
    <footer className="mx-auto mt-8 max-w-3xl border-t border-ink-700/40 px-4 pt-6 pb-24 md:pb-3 text-[11px] text-text-muted">
      <nav className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1">
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
        <span aria-hidden>·</span>
        <Link
          href="/standards"
          className="underline decoration-dotted underline-offset-2 hover:text-text-secondary"
        >
          Standards
        </Link>
        <span aria-hidden>·</span>
        <Link
          href="/contact"
          className="underline decoration-dotted underline-offset-2 hover:text-text-secondary"
        >
          Contact
        </Link>
        <span aria-hidden>·</span>
        <Link
          href="/privacy"
          className="underline decoration-dotted underline-offset-2 hover:text-text-secondary"
        >
          Privacy
        </Link>
        <span aria-hidden>·</span>
        <Link
          href="/terms"
          className="underline decoration-dotted underline-offset-2 hover:text-text-secondary"
        >
          Terms
        </Link>
      </nav>
    </footer>
  );
}
