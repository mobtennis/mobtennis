"use client";

/**
 * Drives Ezoic's per-page placeholder lifecycle on App Router
 * navigations. Without this, sa.min.js fills placeholders once on
 * initial load and leaves every client-side route change blank.
 *
 * Pattern is the one Ezoic's Next.js doc recommends: on every
 * pathname change, queue `destroyPlaceholders()` then
 * `requestAnimationFrame(showAds())`. The rAF gives React a tick to
 * finish painting the new page's placeholder divs before Ezoic
 * scans the DOM.
 *
 * Renders nothing and short-circuits when the network is not Ezoic —
 * safe to mount unconditionally in the root layout.
 */

import { usePathname } from "next/navigation";
import { useEffect } from "react";

const NETWORK = process.env.NEXT_PUBLIC_AD_NETWORK;

export function EzoicRouteHandler() {
  const pathname = usePathname();

  useEffect(() => {
    if (NETWORK !== "ezoic") return;
    if (typeof window === "undefined") return;

    // `ezstandalone.cmd` is the queue created by `ezoic-init`. Pushing
    // here is safe whether sa.min.js has loaded yet or not — the queue
    // is flushed on load and then runs callbacks synchronously.
    const ez = window.ezstandalone;
    if (!ez || !ez.cmd) return;

    ez.cmd.push(() => {
      ez.destroyPlaceholders();
      requestAnimationFrame(() => {
        ez.showAds();
      });
    });
  }, [pathname]);

  return null;
}
