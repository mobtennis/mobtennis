"use client";

import { useEffect } from "react";

/**
 * One-shot kick to AdSense's queue per <ins> render. Mounted alongside
 * each AdSlot in live mode — AdSense looks for empty `.adsbygoogle` ins
 * elements and fills them when something gets pushed onto its array.
 *
 * Wrapped in a try/catch because the script can be blocked (uBlock,
 * Brave, content blockers) and we'd rather not surface a JS error.
 */
declare global {
  interface Window {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    adsbygoogle?: any[];
  }
}

export function AdSenseInit() {
  useEffect(() => {
    try {
      (window.adsbygoogle = window.adsbygoogle || []).push({});
    } catch {
      /* ad blocker / load failure — ignore */
    }
  }, []);
  return null;
}
