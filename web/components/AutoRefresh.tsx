"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

type Props = {
  /** Polling interval. Default 30s — fine for tournament-level pages.
   * Drop to 10s for a single live-match page. */
  intervalMs?: number;
  /** Set to false (typical: status !== "live") to skip the timer entirely
   * and avoid hammering Vercel revalidation when nothing's changing. */
  enabled?: boolean;
};

/**
 * Triggers `router.refresh()` on a timer. router.refresh() re-runs the
 * server component's fetch + render but preserves React state and scroll
 * position — much smoother than a full page reload. Server-rendered pages
 * stay statically generated for SEO; this just keeps live data fresh while
 * the user has the tab open.
 */
export function AutoRefresh({ intervalMs = 30_000, enabled = true }: Props) {
  const router = useRouter();
  useEffect(() => {
    if (!enabled) return;
    const id = setInterval(() => router.refresh(), intervalMs);
    return () => clearInterval(id);
  }, [enabled, intervalMs, router]);
  return null;
}
