import Link from "next/link";
import { notFound } from "next/navigation";

import { api, type SpotTheBallSet } from "@/lib/api";
import { SpotTheBallRound } from "@/components/SpotTheBallRound";

export const revalidate = 300;

export const metadata = {
  title: "Spot the ball",
  description: "Five tennis action shots, ball removed. One click each, cumulative score.",
};

export default async function SpotTheBallTodayPage() {
  const today = await api<SpotTheBallSet>(
    "/api/spot-the-ball/today",
    { revalidate: 300 },
  ).catch(() => null);
  if (!today || today.images.length === 0) notFound();

  return (
    <div className="space-y-6">
      <SpotTheBallRound set={today} />
      <div className="flex gap-4 text-sm">
        <Link
          href="/play/spot-the-ball/archive"
          className="font-medium text-accent hover:text-accent-dim"
        >
          Past rounds →
        </Link>
      </div>
    </div>
  );
}
