import Link from "next/link";
import { notFound } from "next/navigation";

import { api, type SpotTheBallPuzzle } from "@/lib/api";
import { SpotTheBall } from "@/components/SpotTheBall";

// Past puzzles are immutable once the ball is calibrated. Long
// cache is fine; admin re-calibration via the route below bypasses
// this fetch by re-rendering server-side anyway.
export const revalidate = 3600;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ date: string }>;
}) {
  const { date } = await params;
  return { title: `Spot the ball · ${date}` };
}

export default async function SpotTheBallByDate({
  params,
  searchParams,
}: {
  params: Promise<{ date: string }>;
  searchParams: Promise<{ calibrate?: string }>;
}) {
  const { date } = await params;
  const { calibrate } = await searchParams;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) notFound();

  // In calibrate mode, hit the admin endpoint — bypasses the
  // is_published gate so we can edit queued puzzles before they go
  // live. Out of calibrate mode, use the public endpoint which only
  // returns inpainted/published puzzles.
  const fetchPath = calibrate
    ? `/api/admin/spot-the-ball/by-date/${date}?key=${encodeURIComponent(calibrate)}`
    : `/api/spot-the-ball/${date}`;
  const puzzle = await api<SpotTheBallPuzzle>(
    fetchPath,
    { revalidate: 0 },
  ).catch(() => null);
  if (!puzzle) notFound();

  return (
    <div className="space-y-6">
      <SpotTheBall puzzle={puzzle} calibrateKey={calibrate} />
      <div className="flex gap-4 text-sm">
        <Link href="/play/spot-the-ball" className="font-medium text-accent hover:text-accent-dim">
          ← Today's puzzle
        </Link>
        <Link href="/play/spot-the-ball/archive" className="font-medium text-accent hover:text-accent-dim">
          All past puzzles →
        </Link>
      </div>
    </div>
  );
}
