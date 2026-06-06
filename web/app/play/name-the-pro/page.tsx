import Link from "next/link";
import { notFound } from "next/navigation";

import { api, type NameTheProSet } from "@/lib/api";
import { NameTheProRound } from "@/components/NameTheProRound";

export const revalidate = 300;

export const metadata = {
  title: "Name the pro",
  description: "Five tennis photos, four guesses each. Cumulative score, daily set.",
};

export default async function NameTheProTodayPage() {
  const today = await api<NameTheProSet>(
    "/api/name-the-pro/today",
    { revalidate: 300 },
  ).catch(() => null);
  if (!today || today.images.length === 0) notFound();

  return (
    <div className="space-y-6">
      <NameTheProRound set={today} />
      <div className="flex gap-4 text-sm">
        <Link
          href="/play/name-the-pro/archive"
          className="font-medium text-accent hover:text-accent-dim"
        >
          Past rounds →
        </Link>
      </div>
    </div>
  );
}
