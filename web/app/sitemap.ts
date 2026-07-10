import type { MetadataRoute } from "next";

import {
  api,
  type DigestSummary,
  type PlayerSummary,
  type RivalryPair,
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
 * H2H pages: we DON'T list every N² pair (a crawl-budget sink), but the
 * marquee long tail — pairs that actually met 2+ times, both recognisable
 * players — is one of the highest-intent tennis search patterns
 * ("X vs Y h2h"), so we enumerate those via /api/h2h/rivalries. Players
 * appearing in a rivalry are also added to the player-page set, which is
 * how retired greats (Federer, Djokovic, …) get in — the ranked-players
 * list is ordered by *current* rank, so they'd otherwise never appear.
 *
 * Intentionally excluded:
 *   - Individual match pages — high volume, low standalone editorial
 *     value; linked from tournament + player + H2H pages, which are
 *     where a reader actually lands.
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

  const [digests, atpPlayers, wtaPlayers, tournaments, pairs] = await Promise.all([
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
    api<RivalryPair[]>("/api/h2h/rivalries?min_meetings=2", {
      revalidate: 3600,
    }).catch(() => [] as RivalryPair[]),
  ]);

  const digestPages: MetadataRoute.Sitemap = digests.map((d) => ({
    url: `${BASE}/digest/${d.week_start}`,
    lastModified: new Date(d.generated_at),
    changeFrequency: "yearly",
    priority: 0.7,
  }));

  // H2H pages — marquee rivalries only (see docstring). Slugs come back
  // alphabetically ordered so each pair is one canonical URL.
  const h2hPages: MetadataRoute.Sitemap = pairs.map((p) => ({
    url: `${BASE}/h2h/${p.slug1}-vs-${p.slug2}`,
    lastModified: now,
    changeFrequency: "monthly",
    priority: 0.6,
  }));

  // Player pages: the ranked list (top 200/tour, ordered by current rank)
  // UNION every player who appears in a rivalry — that's how retired
  // greats, who have no current rank, get indexed. De-dupe on slug.
  const playerSlugs = new Set<string>();
  for (const p of [...atpPlayers, ...wtaPlayers]) playerSlugs.add(p.slug);
  for (const r of pairs) {
    playerSlugs.add(r.slug1);
    playerSlugs.add(r.slug2);
  }
  const playerPages: MetadataRoute.Sitemap = [...playerSlugs].map((slug) => ({
    url: `${BASE}/players/${slug}`,
    lastModified: now,
    changeFrequency: "weekly",
    priority: 0.7,
  }));

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

  return [
    ...staticPages,
    ...digestPages,
    ...tournamentPages,
    ...playerPages,
    ...h2hPages,
  ];
}
