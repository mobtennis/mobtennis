import type { Metadata, Viewport } from "next";
import Script from "next/script";

import "@/styles/globals.css";
import { AnalyticsInit } from "@/components/AnalyticsInit";
import { BottomNav } from "@/components/BottomNav";
import { Footer } from "@/components/Footer";
import { TopBar } from "@/components/TopBar";

// Ad-network loader selection. AdSense is the only supported live
// network; "off" disables everything. Set NEXT_PUBLIC_AD_NETWORK
// explicitly, or rely on the legacy fallback (AdSense iff
// ADSENSE_CLIENT_ID is configured).
const AD_CLIENT_ID = process.env.NEXT_PUBLIC_ADSENSE_CLIENT_ID;
const AD_NETWORK: "adsense" | "off" =
  (process.env.NEXT_PUBLIC_AD_NETWORK as "adsense" | "off" | undefined) ??
  (AD_CLIENT_ID ? "adsense" : "off");

// Google Ads conversion-tracking tag. Renders on every page so a click
// from any campaign — regardless of which URL the ad lands on — fires
// the gtag and is attributable. Env-var override leaves the default in
// code so a fresh deploy works without Vercel env config; set
// NEXT_PUBLIC_GOOGLE_ADS_ID="" to disable.
const GOOGLE_ADS_ID =
  process.env.NEXT_PUBLIC_GOOGLE_ADS_ID ?? "AW-18177033731";

export const metadata: Metadata = {
  title: { default: "Mob Tennis — Every match. Every story.", template: "%s · Mob Tennis" },
  description:
    "Live ATP & WTA scores, player profiles, tournament draws, head-to-head, news. Fan-first, fast, clean.",
  applicationName: "Mob Tennis",
  appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: "Mob Tennis" },
  // AdSense site verification — static claim of ownership for Google's
  // crawlers, independent of whether the loader script is currently
  // mounted on the page.
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
        <TopBar />
        {/* No bottom padding on `main` — the Footer below owns the
            clearance for the mobile BottomNav (pb-24 there). Setting
            it on both produced a giant gap between the last content
            card and the footer border on mobile. */}
        <main className="mx-auto max-w-3xl px-3 pt-3">{children}</main>
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
