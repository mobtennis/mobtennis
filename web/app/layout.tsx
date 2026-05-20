import type { Metadata, Viewport } from "next";
import Script from "next/script";

import "@/styles/globals.css";
import { AnalyticsInit } from "@/components/AnalyticsInit";
import { BottomNav } from "@/components/BottomNav";
import { EzoicRouteHandler } from "@/components/EzoicRouteHandler";
import { EzoicScripts } from "@/components/EzoicScripts";
import { Footer } from "@/components/Footer";
import { TopBar } from "@/components/TopBar";

// Ad-network loader selection. Explicit NEXT_PUBLIC_AD_NETWORK wins; the
// legacy fallback ("AdSense iff ADSENSE_CLIENT_ID is set, else nothing") is
// preserved so existing deployments keep working without touching env.
const AD_CLIENT_ID = process.env.NEXT_PUBLIC_ADSENSE_CLIENT_ID;
const AD_NETWORK: "adsense" | "ezoic" | "off" =
  (process.env.NEXT_PUBLIC_AD_NETWORK as "adsense" | "ezoic" | "off" | undefined) ??
  (AD_CLIENT_ID ? "adsense" : "off");

// Google Ads conversion-tracking tag. Renders on every page so a click
// from any campaign — regardless of which URL the ad lands on — fires
// the gtag and is attributable. Env-var override leaves the default in
// code so a fresh deploy works without Vercel env config; set
// NEXT_PUBLIC_GOOGLE_ADS_ID="" to disable.
const GOOGLE_ADS_ID =
  process.env.NEXT_PUBLIC_GOOGLE_ADS_ID ?? "AW-18177033731";

export const metadata: Metadata = {
  title: { default: "Mobtennis — live tennis, your way", template: "%s · Mobtennis" },
  description:
    "Live ATP & WTA scores, player profiles, tournament draws, head-to-head, news. Fan-first, fast, clean.",
  applicationName: "Mobtennis",
  appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: "Mobtennis" },
  // AdSense site verification — gives Google an unambiguous signal that
  // this domain belongs to our publisher account, even before the loader
  // script is allowed to run on the page. Keep this even when ads are
  // currently served via Ezoic; it's a static claim about ownership and
  // makes flipping back to AdSense later a one-env-var change.
  other: {
    "google-adsense-account": "ca-pub-4959082323175364",
  },
};

export const viewport: Viewport = {
  themeColor: "#FAF7F0",
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AnalyticsInit />
        {/* No-op unless AD_NETWORK=ezoic. Drives the per-route
            placeholder lifecycle (destroyPlaceholders → showAds) on
            App Router navigations. */}
        <EzoicRouteHandler />
        <TopBar />
        <main className="mx-auto max-w-3xl px-3 pt-3 pb-24 md:pb-8">{children}</main>
        <Footer />
        <BottomNav />
        {/* AdSense loader: served only when the active network is AdSense
            AND the publisher ID is configured. async + afterInteractive
            so it doesn't block first paint. */}
        {AD_NETWORK === "adsense" && AD_CLIENT_ID && (
          <Script
            src={`https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${AD_CLIENT_ID}`}
            strategy="afterInteractive"
            crossOrigin="anonymous"
            async
          />
        )}
        {/* Ezoic — CMP scripts, ezstandalone queue init, sa.min.js loader,
            and analytics.js. Renders nothing unless AD_NETWORK=ezoic, so
            switching networks is one env var. */}
        <EzoicScripts />

        {/* Google Ads gtag — conversion attribution for paid campaigns.
            afterInteractive so it doesn't block first paint. The two
            scripts mirror exactly what Google Ads dashboard exports. */}
        {GOOGLE_ADS_ID && (
          <>
            <Script
              id="google-ads-loader"
              src={`https://www.googletagmanager.com/gtag/js?id=${GOOGLE_ADS_ID}`}
              strategy="afterInteractive"
              async
            />
            <Script id="google-ads-init" strategy="afterInteractive">
              {`window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(arguments);}
gtag('js', new Date());
gtag('config', '${GOOGLE_ADS_ID}');`}
            </Script>
          </>
        )}
      </body>
    </html>
  );
}
