import Link from "next/link";
import { notFound } from "next/navigation";

import { api, type CallTheShotSet } from "@/lib/api";
import { CallTheShotRound } from "@/components/CallTheShotRound";

export const revalidate = 300;

export const metadata = {
  title: "Call the shot",
  description: "Watch the rally, predict where the next shot is going.",
};

export default async function CallTheShotPage() {
  const today = await api<CallTheShotSet>("/api/call-the-shot/today", {
    revalidate: 300,
  }).catch(() => null);
  if (!today || today.items.length === 0) notFound();

  return (
    <div className="space-y-6">
      <CallTheShotRound set={today} />
      <div className="flex gap-4 text-sm">
        <Link
          href="/play/call-the-shot/archive"
          className="font-medium text-accent hover:text-accent-dim"
        >
          Past rounds →
        </Link>
      </div>
    </div>
  );
}
