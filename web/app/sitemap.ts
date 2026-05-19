import type { MetadataRoute } from "next";

import {
  api,
  type DigestSummary,
  type PlayerSummary,
  type TournamentSummary,
} from "@/lib/api";

const BASE = "https://mob.tennis";

// Cache the generated sitemap. Tournaments + players don't change minute-
// to-minute; an hour is generous and keeps build-time work light.
export const revalidate = 3600;

/**
 * Sitemap for crawlers. Lists the canonical editorial pages and the
 * highest-signal dynamic pages: top-ranked players (where the prose
 * snapshot has substance), the tournament brand pages, and every
 * weekly digest in the archive.
 *
 * Intentionally excluded:
 *   - Individual match pages — high volume, low standalone editorial
 *     value; linked from tournament + player + H2H pages, which are
 *     where a reader actually lands.
 *   - H2H pages — crawled organically from player pages; including
 *     every pair is a combinatorial explosion.
 *   - Per-year tournament editions — the brand page already aggregates
 *     enough history; year pages are reachable via that.
 */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date();

  // ---- Static editorial pages ---------------------------------------------

  const staticPages: MetadataRoute.Sitemap = [
    { url: BASE, changeFrequency: "hourly", priority: 1.0, lastModified: now },
    { url: `${BASE}/about`, changeFrequency: "monthly", priority: 0.8, lastModified: now },
    { url: `${BASE}/standards`, changeFrequency: "monthly", priority: 0.7, lastModified: now },
    { url: `${BASE}/contact`, changeFrequency: "monthly", priority: 0.6, lastModified: now },
    { url: `${BASE}/privacy`, changeFrequency: "monthly", priority: 0.4, lastModified: now },
    { url: `${BASE}/terms`, changeFrequency: "monthly", priority: 0.4, lastModified: now },
    { url: `${BASE}/credits`, changeFrequency: "monthly", priority: 0.4, lastModified: now },
    { url: `${BASE}/digest`, changeFrequency: "weekly", priority: 0.9, lastModified: now },
    { url: `${BASE}/news`, changeFrequency: "hourly", priority: 0.8, lastModified: now },
    { url: `${BASE}/rankings`, changeFrequency: "weekly", priority: 0.8, lastModified: now },
    { url: `${BASE}/tournaments`, changeFrequency: "daily", priority: 0.9, lastModified: now },
  ];

  // ---- Dynamic pages — best-effort, sitemap shouldn't break the build ----

  const [digests, atpPlayers, wtaPlayers, tournaments] = await Promise.all([
    api<DigestSummary[]>("/api/digests?limit=100", { revalidate: 3600 }).catch(
      () => [] as DigestSummary[],
    ),
    api<PlayerSummary[]>("/api/players?tour=atp&limit=200", {
      revalidate: 3600,
    }).catch(() => [] as PlayerSummary[]),
    api<PlayerSummary[]>("/api/players?tour=wta&limit=200", {
      revalidate: 3600,
    }).catch(() => [] as PlayerSummary[]),
    api<TournamentSummary[]>("/api/tournaments?limit=200", {
      revalidate: 3600,
    }).catch(() => [] as TournamentSummary[]),
  ]);

  const digestPages: MetadataRoute.Sitemap = digests.map((d) => ({
    url: `${BASE}/digest/${d.week_start}`,
    lastModified: new Date(d.generated_at),
    changeFrequency: "yearly",
    priority: 0.7,
  }));

  const playerPages: MetadataRoute.Sitemap = [...atpPlayers, ...wtaPlayers].map(
    (p) => ({
      url: `${BASE}/players/${p.slug}`,
      lastModified: now,
      changeFrequency: "weekly",
      priority: 0.7,
    }),
  );

  // De-duplicate by (tour, slug) — the API returns one row per edition, but
  // the page route is the brand page that aggregates them.
  const tournamentBrands = new Map<string, TournamentSummary>();
  for (const t of tournaments) {
    const key = `${t.tour}/${t.slug}`;
    if (!tournamentBrands.has(key)) tournamentBrands.set(key, t);
  }
  const tournamentPages: MetadataRoute.Sitemap = [...tournamentBrands.values()].map(
    (t) => ({
      url: `${BASE}/tournaments/${t.tour}/${t.slug}`,
      lastModified: now,
      changeFrequency: "weekly",
      priority: 0.8,
    }),
  );

  return [...staticPages, ...digestPages, ...tournamentPages, ...playerPages];
}
