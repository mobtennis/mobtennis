import type { NextConfig } from "next";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  images: { remotePatterns: [{ protocol: "https", hostname: "**" }] },
  async rewrites() {
    return {
      beforeFiles: [],
      afterFiles: [
        { source: "/api/proxy/:path*", destination: `${API_BASE}/api/:path*` },
      ],
      fallback: [],
    };
  },
};

export default nextConfig;
