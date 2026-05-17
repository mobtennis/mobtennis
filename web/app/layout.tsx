import type { Metadata, Viewport } from "next";
import Script from "next/script";

import "@/styles/globals.css";
import { AnalyticsInit } from "@/components/AnalyticsInit";
import { BottomNav } from "@/components/BottomNav";
import { Footer } from "@/components/Footer";
import { TopBar } from "@/components/TopBar";

// AdSense loader — only injected when a publisher ID is configured. Loaded
// async with `afterInteractive` strategy so it doesn't block first paint.
const AD_CLIENT_ID = process.env.NEXT_PUBLIC_ADSENSE_CLIENT_ID;

export const metadata: Metadata = {
  title: { default: "Mobtennis — live tennis, your way", template: "%s · Mobtennis" },
  description:
    "Live ATP & WTA scores, player profiles, tournament draws, head-to-head, news. Fan-first, fast, clean.",
  applicationName: "Mobtennis",
  appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: "Mobtennis" },
  // AdSense site verification — gives Google an unambiguous signal that
  // this domain belongs to our publisher account, even before the loader
  // script is allowed to run on the page.
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
        {AD_CLIENT_ID && (
          <Script
            src={`https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${AD_CLIENT_ID}`}
            strategy="afterInteractive"
            crossOrigin="anonymous"
            async
          />
        )}
      </body>
    </html>
  );
}
