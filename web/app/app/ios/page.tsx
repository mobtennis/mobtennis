import Link from "next/link";

export const metadata = { title: "Mobtennis for iOS" };

export default function IosPage() {
  return (
    <article className="space-y-4 pt-2">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">Mobtennis for iOS</h1>
        <p className="mt-1 text-sm text-text-secondary">Coming to the App Store soon.</p>
      </header>

      <section className="rounded-lg border border-ink-700 bg-ink-900 p-4 shadow-card">
        <p className="text-sm text-text-secondary">
          It&apos;s early days — we&apos;re hoping to have the iOS app published
          in the next couple of days. Until then, the full Mobtennis experience
          works in your mobile browser.
        </p>
        <Link
          href="/"
          className="mt-3 inline-block text-sm font-medium text-accent hover:text-accent-dim"
        >
          ← Back to live scores
        </Link>
      </section>
    </article>
  );
}
