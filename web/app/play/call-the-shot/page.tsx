import { notFound } from "next/navigation";

import { api, type CallTheShotItem } from "@/lib/api";
import { CallTheShotRound } from "@/components/CallTheShotRound";

export const revalidate = 60;

export const metadata = {
  title: "Call the shot",
  description: "Watch the rally, predict where the next shot is going.",
};

type ApiItem = {
  id: number;
  video_id: string;
  start_at_s: number;
  pause_at_s: number;
  caption: string;
  options: string[];
  correct_index: number;
  source_url: string | null;
};

export default async function CallTheShotPage() {
  const rows = await api<ApiItem[]>("/api/call-the-shot/items", {
    revalidate: 60,
  }).catch(() => [] as ApiItem[]);

  if (!rows.length) notFound();

  const items: CallTheShotItem[] = rows.map((r) => ({
    id: String(r.id),
    video_id: r.video_id,
    start_at_s: r.start_at_s,
    pause_at_s: r.pause_at_s,
    caption: r.caption,
    options: [
      r.options[0] ?? "",
      r.options[1] ?? "",
      r.options[2] ?? "",
      r.options[3] ?? "",
    ],
    correct_index: Math.max(0, Math.min(3, r.correct_index)) as 0 | 1 | 2 | 3,
    source_url: r.source_url ?? undefined,
  }));

  return (
    <div className="space-y-6">
      <CallTheShotRound items={items} />
    </div>
  );
}
