import type { MetadataRoute } from "next";

/**
 * Standard robots policy. We allow everything except:
 *   - /api/*          — proxy paths; not pages.
 *   - /search         — query-string-driven; every search produces a
 *                       unique URL with no editorial content.
 *   - /following      — per-device personalisation; nothing to index.
 *   - /h2h/*-vs-      — half-formed URLs (anchor on one side only).
 *                       The page falls back to an opponent picker, but
 *                       there's no editorial content to crawl.
 *
 * Sitemap pointer goes here too — that's how the canonical contract
 * with crawlers gets registered.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: ["/api/", "/search", "/following", "/h2h/*-vs-$"],
      },
    ],
    sitemap: "https://mob.tennis/sitemap.xml",
    host: "https://mob.tennis",
  };
}
