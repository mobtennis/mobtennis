import Link from "next/link";
import { notFound } from "next/navigation";

import { api, type CallTheShotSet } from "@/lib/api";
import { CallTheShotRound } from "@/components/CallTheShotRound";

export const revalidate = 3600;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return { title: `Call the shot · round ${id}` };
}

export default async function CallTheShotSetPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();
  const set = await api<CallTheShotSet>(`/api/call-the-shot/${id}`, {
    revalidate: 3600,
  }).catch(() => null);
  if (!set || set.items.length === 0) notFound();

  return (
    <div className="space-y-6">
      <CallTheShotRound set={set} />
      <div className="flex gap-4 text-sm">
        <Link
          href="/play/call-the-shot"
          className="font-medium text-accent hover:text-accent-dim"
        >
          ← Today's round
        </Link>
        <Link
          href="/play/call-the-shot/archive"
          className="font-medium text-accent hover:text-accent-dim"
        >
          All past rounds →
        </Link>
      </div>
    </div>
  );
}
