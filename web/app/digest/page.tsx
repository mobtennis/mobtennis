import { notFound, redirect } from "next/navigation";

import { api, type DigestDetail } from "@/lib/api";

export const metadata = {
  title: "This week in tennis",
  description:
    "A weekly recap of the past seven days on the ATP and WTA tours — finals, upsets, and what's coming next.",
};

/**
 * Lands on the latest digest. We redirect to the dated archive URL so
 * the canonical URL for the week is `/digest/[week]` — better for
 * indexing and for users sharing links.
 */
export default async function DigestIndex() {
  const latest = await api<DigestDetail>("/api/digests/latest", {
    revalidate: 600,
  }).catch(() => null);
  if (!latest) notFound();
  redirect(`/digest/${latest.week_start}`);
}
