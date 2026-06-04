import Link from "next/link";
import { notFound } from "next/navigation";

import { api, type SpotTheBallPuzzle } from "@/lib/api";
import { SpotTheBall } from "@/components/SpotTheBall";

// Daily puzzle — the rotating one. Cache short so a new day's
// puzzle becomes visible without a deploy.
export const revalidate = 300;

export const metadata = {
  title: "Spot the ball",
  description: "Where's the tennis ball? One click to lock it in.",
};

export default async function SpotTheBallTodayPage() {
  const puzzle = await api<SpotTheBallPuzzle>(
    "/api/spot-the-ball/today",
    { revalidate: 300 },
  ).catch(() => null);
  if (!puzzle) notFound();

  return (
    <div className="space-y-6">
      <SpotTheBall puzzle={puzzle} />
      <Link
        href="/play/spot-the-ball/archive"
        className="inline-block text-sm font-medium text-accent hover:text-accent-dim"
      >
        Past puzzles →
      </Link>
    </div>
  );
}
