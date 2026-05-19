/**
 * Mounts every <script> tag Ezoic requires per their getting-started
 * docs (docs.ezoic.com/docs/ezoicads/integration). Renders nothing
 * unless NEXT_PUBLIC_AD_NETWORK = "ezoic", so flipping the network
 * env back to "adsense" / "off" cleanly removes the entire dependency
 * tree without touching any page code.
 *
 * Removing Ezoic later:
 *   1. Set NEXT_PUBLIC_AD_NETWORK to "adsense" or "off"
 *   2. Delete this file and `components/EzoicRouteHandler.tsx`
 *   3. Remove the <EzoicScripts /> + <EzoicRouteHandler /> imports
 *      from `app/layout.tsx`
 *   4. Remove the `ezoic` branch in `components/AdSlot.tsx`
 *   5. Remove the conditional `/ads.txt` rewrite in `next.config.ts`
 *   6. Delete `types/ezoic.d.ts`
 */

import Script from "next/script";

const NETWORK = process.env.NEXT_PUBLIC_AD_NETWORK;

export function EzoicScripts() {
  if (NETWORK !== "ezoic") return null;

  return (
    <>
      {/* All five tags use `beforeInteractive` so Next.js hoists them
          into <head> regardless of where <EzoicScripts /> is mounted in
          the layout tree. Ezoic's integration check (and their JS
          debugger at ?ez_js_debugger=1) explicitly looks for these in
          <head>; with `afterInteractive` they would land in <body> and
          the incubation test fails silently.

          Order + `data-cfasync="false"` follow the Ezoic Next.js doc
          verbatim. `data-cfasync="false"` keeps Cloudflare Rocket
          Loader (or similar optimizers) from reordering / deferring
          the CMP scripts, which must run before any ad/tracking JS so
          we don't process personal data pre-consent. */}
      <Script
        id="ezoic-cmp-min"
        src="https://cmp.gatekeeperconsent.com/min.js"
        strategy="beforeInteractive"
        data-cfasync="false"
      />
      <Script
        id="ezoic-cmp"
        src="https://the.gatekeeperconsent.com/cmp.min.js"
        strategy="beforeInteractive"
        data-cfasync="false"
      />

      {/* Standalone ads loader — handles bidding + placement filling.
          Domain is identified by hostname when the script runs; no
          per-site ID needs to be supplied in the URL. */}
      <Script
        id="ezoic-sa"
        src="https://www.ezojs.com/ezoic/sa.min.js"
        strategy="beforeInteractive"
      />

      {/* ezstandalone command queue. Source-order after sa.min.js per
          Ezoic's reference; the `|| {}` / `|| []` guards make this
          order-independent in practice. */}
      <Script id="ezoic-init" strategy="beforeInteractive">
        {`window.ezstandalone = window.ezstandalone || {};
window.ezstandalone.cmd = window.ezstandalone.cmd || [];`}
      </Script>

      {/* Ezoic Analytics — revenue attribution + split-testing. Required
          per the getting-started checklist. */}
      <Script
        id="ezoic-analytics"
        src="https://ezoicanalytics.com/analytics.js"
        strategy="beforeInteractive"
      />
    </>
  );
}
