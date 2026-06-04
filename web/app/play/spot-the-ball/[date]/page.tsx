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

  const puzzle = await api<SpotTheBallPuzzle>(
    `/api/spot-the-ball/${date}`,
    // Calibration mode hits the public endpoint, which requires the
    // puzzle to already be visible. If you're seeding a fresh row
    // without coords, set ball_x_pct = 50.0 in the seed to make it
    // visible, then calibrate to the real position via the click.
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
