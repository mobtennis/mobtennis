import { SpotTheBallQueue } from "@/components/SpotTheBallQueue";

export const revalidate = 0;

export const metadata = {
  title: "Spot the ball · queue",
  robots: { index: false, follow: false },
};

export default async function SpotTheBallQueuePage({
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
  return <SpotTheBallQueue adminKey={key} />;
}
