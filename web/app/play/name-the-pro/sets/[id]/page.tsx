import Link from "next/link";
import { notFound } from "next/navigation";

import { api, type NameTheProSet } from "@/lib/api";
import { NameTheProRound } from "@/components/NameTheProRound";

export const revalidate = 3600;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return { title: `Name the pro · round ${id}` };
}

export default async function NameTheProSetPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();
  const set = await api<NameTheProSet>(
    `/api/name-the-pro/${id}`,
    { revalidate: 3600 },
  ).catch(() => null);
  if (!set || set.images.length === 0) notFound();

  return (
    <div className="space-y-6">
      <NameTheProRound set={set} />
      <div className="flex gap-4 text-sm">
        <Link
          href="/play/name-the-pro"
          className="font-medium text-accent hover:text-accent-dim"
        >
          ← Today's round
        </Link>
        <Link
          href="/play/name-the-pro/archive"
          className="font-medium text-accent hover:text-accent-dim"
        >
          All past rounds →
        </Link>
      </div>
    </div>
  );
}
