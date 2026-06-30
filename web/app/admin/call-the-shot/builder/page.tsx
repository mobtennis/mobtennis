import { CallTheShotBuilder } from "@/components/CallTheShotBuilder";

// Admin-only — robots noindex + revalidate=0 so it's always live.
export const revalidate = 0;

export const metadata = {
  title: "Call the shot · builder",
  robots: { index: false, follow: false },
};

export default async function CallTheShotBuilderPage({
  searchParams,
}: {
  searchParams: Promise<{ key?: string }>;
}) {
  const { key } = await searchParams;
  if (!key) {
    return (
      <div className="space-y-3 p-4 text-sm">
        <h1 className="text-lg font-semibold">Admin key required</h1>
        <p className="text-text-secondary">
          Append <code>?key=…</code> to the URL with the configured ADMIN_KEY.
        </p>
      </div>
    );
  }
  // Phase 1 has no backend writes — the page just outputs a TS snippet
  // for the operator to paste into the data file. Any non-empty key
  // passes the gate; this is just to keep the page off public surfaces.
  return <CallTheShotBuilder />;
}
