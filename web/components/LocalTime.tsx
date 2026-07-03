"use client";

import { useEffect, useState } from "react";

import { formatDate, formatMatchTime, formatTime, parseUtcIso } from "@/lib/format";

/**
 * Renders a UTC timestamp in the viewer's local timezone. Necessary
 * because the components that use it (MatchCard, match detail page,
 * tournament pages) are Server Components, which means their SSR
 * render happens on Vercel — UTC. `.toLocaleTimeString()` there
 * returns UTC-formatted strings, so users outside UTC see the wrong
 * time until the client rehydrates.
 *
 * SSR path: render the UTC value inside a stable wrapper. First
 * client render replaces it with the local version. `suppressHydra-
 * tionWarning` because the two intentionally differ.
 */

type Variant = "time" | "match" | "date";

function formatFor(variant: Variant, iso: string | null): string {
  if (!iso) return "";
  switch (variant) {
    case "match": return formatMatchTime(iso);
    case "date":  return formatDate(iso);
    case "time":
    default:      return formatTime(iso);
  }
}


// Server-side fallback: render UTC HH:MM so the SSR HTML at least
// carries a stable-shaped string. The client swap will replace it.
function ssrFallback(variant: Variant, iso: string | null): string {
  if (!iso) return "";
  const d = parseUtcIso(iso);
  if (Number.isNaN(d.getTime())) return "";
  if (variant === "date") {
    return d.toLocaleDateString("en-GB", { month: "short", day: "numeric", timeZone: "UTC" });
  }
  const hh = String(d.getUTCHours()).padStart(2, "0");
  const mm = String(d.getUTCMinutes()).padStart(2, "0");
  return `${hh}:${mm} UTC`;
}


export function LocalTime({
  iso,
  variant = "time",
  fallback = "",
  className,
}: {
  iso: string | null;
  variant?: Variant;
  fallback?: string;
  className?: string;
}) {
  const [rendered, setRendered] = useState<string>(() =>
    iso ? ssrFallback(variant, iso) : fallback,
  );

  useEffect(() => {
    setRendered(iso ? formatFor(variant, iso) : fallback);
  }, [iso, variant, fallback]);

  return (
    <span className={className} suppressHydrationWarning>
      {rendered || fallback}
    </span>
  );
}
