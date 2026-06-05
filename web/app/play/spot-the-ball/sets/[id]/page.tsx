import Link from "next/link";
import { notFound } from "next/navigation";

import { api, type SpotTheBallSet } from "@/lib/api";
import { SpotTheBallRound } from "@/components/SpotTheBallRound";

export const revalidate = 3600;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return { title: `Spot the ball · round ${id}` };
}

export default async function SpotTheBallSetPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();
  const set = await api<SpotTheBallSet>(
    `/api/spot-the-ball/${id}`,
    { revalidate: 3600 },
  ).catch(() => null);
  if (!set || set.images.length === 0) notFound();

  return (
    <div className="space-y-6">
      <SpotTheBallRound set={set} />
      <div className="flex gap-4 text-sm">
        <Link href="/play/spot-the-ball" className="font-medium text-accent hover:text-accent-dim">
          ← Today's round
        </Link>
        <Link href="/play/spot-the-ball/archive" className="font-medium text-accent hover:text-accent-dim">
          All past rounds →
        </Link>
      </div>
    </div>
  );
}
