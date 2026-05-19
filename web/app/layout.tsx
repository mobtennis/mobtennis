import type { Metadata, Viewport } from "next";
import Script from "next/script";

import "@/styles/globals.css";
import { AnalyticsInit } from "@/components/AnalyticsInit";
import { BottomNav } from "@/components/BottomNav";
import { Footer } from "@/components/Footer";
import { TopBar } from "@/components/TopBar";

// Ad-network loader selection. Explicit NEXT_PUBLIC_AD_NETWORK wins; the
// legacy fallback ("AdSense iff ADSENSE_CLIENT_ID is set, else nothing") is
// preserved so existing deployments keep working without touching env.
const AD_CLIENT_ID = process.env.NEXT_PUBLIC_ADSENSE_CLIENT_ID;
const AD_NETWORK: "adsense" | "ezoic" | "off" =
  (process.env.NEXT_PUBLIC_AD_NETWORK as "adsense" | "ezoic" | "off" | undefined) ??
  (AD_CLIENT_ID ? "adsense" : "off");
const EZOIC_DOMAIN_ID = process.env.NEXT_PUBLIC_EZOIC_DOMAIN_ID;

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
        {/* Ezoic loader (sa.min.js + the per-domain config). Ezoic uses a
            small inline init script to declare the domain ID and then
            pulls their CDN-cached sa.min.js, which handles bidding and
            placeholder filling. The domain ID is the integer they give
            you in the publisher dashboard. */}
        {AD_NETWORK === "ezoic" && EZOIC_DOMAIN_ID && (
          <>
            <Script id="ezoic-init" strategy="beforeInteractive">
              {`window.ezstandalone = window.ezstandalone || {};
ezstandalone.cmd = ezstandalone.cmd || [];`}
            </Script>
            <Script
              src="//www.ezojs.com/ezoic/sa.min.js"
              strategy="afterInteractive"
              async
            />
          </>
        )}
      </body>
    </html>
  );
}
