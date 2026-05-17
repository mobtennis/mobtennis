import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <span className="text-6xl">🎾</span>
      <h1 className="mt-4 text-2xl font-bold">Out</h1>
      <p className="mt-2 text-sm text-text-secondary">That page is out of bounds.</p>
      <Link
        href="/"
        className="mt-4 rounded-full border border-ink-700 px-4 py-2 text-xs font-medium hover:border-ink-600"
      >
        Back to home
      </Link>
    </div>
  );
}
