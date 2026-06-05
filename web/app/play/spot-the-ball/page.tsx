import Link from "next/link";
import { notFound } from "next/navigation";

import { api, type SpotTheBallRound as RoundData } from "@/lib/api";
import { SpotTheBallRound } from "@/components/SpotTheBallRound";

// Daily round. Cache short so a fresh deploy + new puzzles surface
// without waiting on ISR. Round itself is deterministic per UTC
// date — every player gets the same 5 photos.
export const revalidate = 300;

export const metadata = {
  title: "Spot the ball",
  description: "Five tennis action shots, ball removed. One click each, cumulative score.",
};

export default async function SpotTheBallTodayPage() {
  const round = await api<RoundData>(
    "/api/spot-the-ball/round",
    { revalidate: 300 },
  ).catch(() => null);
  if (!round || round.puzzles.length === 0) notFound();

  return (
    <div className="space-y-6">
      <SpotTheBallRound round={round} />
      <div className="flex gap-4 text-sm">
        <Link
          href="/play/spot-the-ball/archive"
          className="font-medium text-accent hover:text-accent-dim"
        >
          Past puzzles →
        </Link>
      </div>
    </div>
  );
}
