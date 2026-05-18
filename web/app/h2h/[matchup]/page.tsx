import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { api, type H2HResponse } from "@/lib/api";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { TournamentGroups } from "@/components/TournamentGroup";
import { SectionHeader } from "@/components/SectionHeader";
import { surfaceColor } from "@/lib/format";

export async function generateMetadata({ params }: { params: Promise<{ matchup: string }> }) {
  const { matchup } = await params;
  return { title: matchup.replace("-vs-", " vs ").replace(/-/g, " ") };
}

export default async function H2HPage({ params }: { params: Promise<{ matchup: string }> }) {
  const { matchup } = await params;
  if (!matchup.includes("-vs-")) notFound();

  // Half-formed URL (`alcaraz-vs-` or `-vs-sinner`): send the user
  // to the opponent picker instead of dead-ending on a 404. Crawlers
  // discovered this URL pattern from old "Compare H2H" buttons; we
  // want any straggling links to land somewhere useful.
  const [s1, s2] = matchup.split("-vs-", 2);
  if (!s1 || !s2) {
    const anchor = s1 || s2;
    redirect(anchor ? `/search?h2h=${anchor}` : "/search");
  }

  const data = await api<H2HResponse>(`/api/h2h/${matchup}`).catch(() => null);
  if (!data) notFound();

  const total = data.p1_wins + data.p2_wins;
  const p1Pct = total ? Math.round((data.p1_wins / total) * 100) : 50;

  return (
    <div className="space-y-6">
      <header className="rounded-lg border border-ink-700 bg-ink-900 p-4 shadow-card">
        <h1 className="text-center text-base font-semibold uppercase tracking-wider text-text-muted">Head-to-Head</h1>
        <div className="mt-3 grid grid-cols-3 items-center gap-3">
          <Link href={`/players/${data.player1.slug}`} className="flex flex-col items-center gap-2">
            <PlayerAvatar name={data.player1.full_name} imageUrl={data.player1.image_url} countryCode={data.player1.country_code} size="md" />
            <span className="line-clamp-1 text-sm font-semibold">{data.player1.full_name}</span>
          </Link>
          <div className="text-center">
            <div className="text-3xl font-bold tnum">
              {data.p1_wins} <span className="text-text-muted">–</span> {data.p2_wins}
            </div>
            <div className="mt-1 text-[10px] uppercase tracking-wider text-text-muted">{total} match{total === 1 ? "" : "es"}</div>
          </div>
          <Link href={`/players/${data.player2.slug}`} className="flex flex-col items-center gap-2">
            <PlayerAvatar name={data.player2.full_name} imageUrl={data.player2.image_url} countryCode={data.player2.country_code} size="md" />
            <span className="line-clamp-1 text-sm font-semibold">{data.player2.full_name}</span>
          </Link>
        </div>

        <div className="mt-4 h-1.5 w-full overflow-hidden rounded-full bg-ink-700">
          <div className="h-full bg-accent transition-all" style={{ width: `${p1Pct}%` }} />
        </div>
      </header>

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
