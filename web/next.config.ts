import type { NextConfig } from "next";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

// When Ezoic is the active ad network, /ads.txt must serve the
// Ezoic-managed authorized-sellers list, not our static AdSense file.
// We transparently rewrite to Ezoic's adstxtmanager URL so the path
// stays on our origin (crawlers that don't follow redirects still see
// the file). Flipping NEXT_PUBLIC_AD_NETWORK away from "ezoic" disables
// the rewrite and the static public/ads.txt takes over again.
const AD_NETWORK = process.env.NEXT_PUBLIC_AD_NETWORK;
const EZOIC_ADSTXT_URL = process.env.NEXT_PUBLIC_EZOIC_ADSTXT_URL;

const nextConfig: NextConfig = {
  reactStrictMode: true,
  images: { remotePatterns: [{ protocol: "https", hostname: "**" }] },
  async rewrites() {
    const rules = [
      { source: "/api/proxy/:path*", destination: `${API_BASE}/api/:path*` },
    ];
    if (AD_NETWORK === "ezoic" && EZOIC_ADSTXT_URL) {
      rules.push({ source: "/ads.txt", destination: EZOIC_ADSTXT_URL });
    }
    return rules;
  },
};

export default nextConfig;
