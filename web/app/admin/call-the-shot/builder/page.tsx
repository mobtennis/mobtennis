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
  // Server-side just gates the route by presence of any key. The key
  // itself is enforced by the FastAPI admin endpoints when the
  // builder writes — wrong key gets a 401 from the API and surfaces
  // as a Save error in the UI.
  return <CallTheShotBuilder adminKey={key} />;
}
