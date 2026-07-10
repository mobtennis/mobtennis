import Link from "next/link";
import { notFound } from "next/navigation";

import { api, type H2HResponse, type PlayerDetail } from "@/lib/api";
import { ChangeOpponentLink } from "@/components/ChangeOpponentLink";
import { H2HOverview } from "@/components/H2HOverview";
import { JsonLd } from "@/components/JsonLd";
import { OpponentPicker } from "@/components/OpponentPicker";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PlayerHoverCard } from "@/components/PlayerHoverCard";
import { TournamentGroups } from "@/components/TournamentGroup";
import { SectionHeader } from "@/components/SectionHeader";
import { surfaceColor } from "@/lib/format";

export async function generateMetadata({ params }: { params: Promise<{ matchup: string }> }) {
  const { matchup } = await params;
  const title = matchup.replace("-vs-", " vs ").replace(/-/g, " ");

  // Noindex two thin shapes: half-formed URLs ("alcaraz-vs-" with one
  // slug missing — page falls back to an opponent picker) and rivalries
  // with zero meetings on record (nothing editorial to anchor on).
  if (!matchup.includes("-vs-")) return { title };
  const [s1, s2] = matchup.split("-vs-", 2);
  if (!s1 || !s2) return { title, robots: { index: false, follow: true } };

  const data = await api<H2HResponse>(`/api/h2h/${matchup}`, { revalidate: 3600 }).catch(
    () => null,
  );
  const totalMeetings = data?.summary?.total_meetings ?? data?.matches.length ?? 0;
  if (!data || totalMeetings === 0) {
    return { title, robots: { index: false, follow: true } };
  }

  const n1 = data.player1.full_name;
  const n2 = data.player2.full_name;
  const richTitle = `${n1} vs ${n2} — Head-to-Head`;
  const description =
    `${n1} vs ${n2}: ${data.p1_wins}–${data.p2_wins} all-time across ` +
    `${totalMeetings} meeting${totalMeetings === 1 ? "" : "s"}. Full head-to-head ` +
    `record, surface breakdown and every past match.`;
  // Canonical = alphabetical slug order, so "a-vs-b" and "b-vs-a"
  // (both linked from player pages) consolidate onto one URL.
  const canonical = `/h2h/${[s1, s2].sort().join("-vs-")}`;
  const og =
    `/api/og/h2h?p1=${encodeURIComponent(n1)}&p2=${encodeURIComponent(n2)}` +
    `&w1=${data.p1_wins}&w2=${data.p2_wins}`;
  return {
    title: richTitle,
    description,
    alternates: { canonical },
    openGraph: {
      title: richTitle,
      description,
      url: canonical,
      images: [{ url: og, width: 1200, height: 630 }],
    },
    twitter: { title: richTitle, description, images: [og] },
  };
}

export default async function H2HPage({ params }: { params: Promise<{ matchup: string }> }) {
  const { matchup } = await params;
  if (!matchup.includes("-vs-")) notFound();

  const [s1, s2] = matchup.split("-vs-", 2);

  // Half-formed URL — render the present player + an inline opponent
  // picker in the other slot. Crawlers / old buttons leave links of
  // this shape; this page used to 404 (or worse, return a random
  // opposite-sex player picked by an empty .contains() match).
  if (!s1 || !s2) {
    const anchor = s1 || s2;
    if (!anchor) notFound();
    const player = await api<PlayerDetail>(`/api/players/${anchor}`).catch(() => null);
    if (!player) notFound();
    const anchorOnLeft = Boolean(s1);
    return (
      <PartialH2HShell
        anchor={player}
        anchorOnLeft={anchorOnLeft}
      />
    );
  }

  const data = await api<H2HResponse>(`/api/h2h/${matchup}`).catch(() => null);
  if (!data) notFound();

  const total = data.p1_wins + data.p2_wins;
  const p1Pct = total ? Math.round((data.p1_wins / total) * 100) : 50;

  return (
    <div className="space-y-6">
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "WebPage",
          name: `${data.player1.full_name} vs ${data.player2.full_name} — Head-to-Head`,
          about: [data.player1, data.player2].map((p) => ({
            "@type": "Person",
            name: p.full_name,
            url: `https://mob.tennis/players/${p.slug}`,
            ...(p.country_code ? { nationality: p.country_code } : {}),
          })),
        }}
      />
      <header className="rounded-lg border border-ink-700 bg-ink-900 p-4 shadow-card">
        <h1 className="text-center text-base font-semibold uppercase tracking-wider text-text-muted">Head-to-Head</h1>
        <div className="mt-3 grid grid-cols-3 items-start gap-3">
          {/* Each side has a "change opponent" link. The anchorSlug
              passed to it is the OTHER player — clicking under
              player 1 swaps player 1 (so player 2 remains the
              anchor), and vice versa. */}
          <div className="flex flex-col items-center gap-2">
            <Link href={`/players/${data.player1.slug}`} className="flex flex-col items-center gap-2">
              <PlayerAvatar name={data.player1.full_name} imageUrl={data.player1.image_url} countryCode={data.player1.country_code} size="md" />
              <span className="line-clamp-1 text-sm font-semibold">
                <PlayerHoverCard slug={data.player1.slug}>{data.player1.full_name}</PlayerHoverCard>
              </span>
            </Link>
            <ChangeOpponentLink anchorSlug={data.player2.slug} tourFilter={data.player2.tour} />
          </div>
          <div className="text-center">
            <div className="text-3xl font-bold tnum">
              {data.p1_wins} <span className="text-text-muted">–</span> {data.p2_wins}
            </div>
            <div className="mt-1 text-[10px] uppercase tracking-wider text-text-muted">{total} match{total === 1 ? "" : "es"}</div>
          </div>
          <div className="flex flex-col items-center gap-2">
            <Link href={`/players/${data.player2.slug}`} className="flex flex-col items-center gap-2">
              <PlayerAvatar name={data.player2.full_name} imageUrl={data.player2.image_url} countryCode={data.player2.country_code} size="md" />
              <span className="line-clamp-1 text-sm font-semibold">
                <PlayerHoverCard slug={data.player2.slug}>{data.player2.full_name}</PlayerHoverCard>
              </span>
            </Link>
            <ChangeOpponentLink anchorSlug={data.player1.slug} tourFilter={data.player1.tour} />
          </div>
        </div>

        <div className="mt-4 h-1.5 w-full overflow-hidden rounded-full bg-ink-700">
          <div className="h-full bg-accent transition-all" style={{ width: `${p1Pct}%` }} />
        </div>
      </header>

      <H2HOverview data={data} />

      {data.surface_splits.length > 0 && (
        <section>
          <SectionHeader title="By surface" />
          <ul className="mt-2 space-y-2">
            {data.surface_splits.map((s) => {
              const t = s.p1_wins + s.p2_wins;
              const pct = t ? Math.round((s.p1_wins / t) * 100) : 50;
              return (
                <li key={s.surface} className="rounded-md border border-ink-700 bg-ink-900 p-3">
                  <div className="flex items-center justify-between text-xs">
                    <span className={`font-bold uppercase tracking-wider ${surfaceColor(s.surface)}`}>{s.surface}</span>
                    <span className="tnum text-text-secondary">
                      {s.p1_wins} – {s.p2_wins}
                    </span>
                  </div>
                  <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-ink-700">
                    <div className="h-full bg-accent" style={{ width: `${pct}%` }} />
                  </div>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {data.matches.length > 0 && (
        <section>
          <SectionHeader title="Past meetings" />
          <div className="mt-2"><TournamentGroups matches={data.matches} /></div>
        </section>
      )}
    </div>
  );
}

/** Half-formed URL layout: known player on one side, autocomplete in
 * the other slot. Score column reads "vs ?" as a prompt rather than
 * pretending we have data. */
function PartialH2HShell({
  anchor,
  anchorOnLeft,
}: {
  anchor: PlayerDetail;
  anchorOnLeft: boolean;
}) {
  const anchorBlock = (
    <Link href={`/players/${anchor.slug}`} className="flex flex-col items-center gap-2">
      <PlayerAvatar
        name={anchor.full_name}
        imageUrl={anchor.image_url}
        countryCode={anchor.country_code}
        size="md"
      />
      <span className="line-clamp-1 text-sm font-semibold">
        <PlayerHoverCard slug={anchor.slug}>{anchor.full_name}</PlayerHoverCard>
      </span>
    </Link>
  );
  const pickerBlock = (
    <div className="flex flex-col items-center gap-2">
      <div className="flex h-14 w-14 items-center justify-center rounded-full border border-dashed border-ink-700 text-2xl text-text-muted">
        ?
      </div>
      <OpponentPicker anchorSlug={anchor.slug} tourFilter={anchor.tour} />
    </div>
  );
  return (
    <div className="space-y-6">
      <header className="rounded-lg border border-ink-700 bg-ink-900 p-4 shadow-card">
        <h1 className="text-center text-base font-semibold uppercase tracking-wider text-text-muted">Head-to-Head</h1>
        <div className="mt-3 grid grid-cols-3 items-start gap-3">
          {anchorOnLeft ? anchorBlock : pickerBlock}
          <div className="text-center text-text-muted">
            <div className="text-3xl font-bold tnum">vs</div>
            <div className="mt-1 text-[10px] uppercase tracking-wider">pick an opponent</div>
          </div>
          {anchorOnLeft ? pickerBlock : anchorBlock}
        </div>
      </header>
    </div>
  );
}
