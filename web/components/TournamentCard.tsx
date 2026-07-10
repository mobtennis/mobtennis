"use client";

import Link from "next/link";

import type { IndexTournament } from "@/lib/api";
import { LiveDot } from "@/components/LiveDot";
import { flagEmoji, surfaceColor } from "@/lib/format";
import { pickTour, usePreferredTour } from "@/lib/preferred-tour";

const CATEGORY_BADGE: Record<string, { label: string; cls: string }> = {
  grand_slam: { label: "GS", cls: "bg-amber-100 text-amber-800 border-amber-200" },
  atp_finals: { label: "Finals", cls: "bg-fuchsia-100 text-fuchsia-800 border-fuchsia-200" },
  wta_finals: { label: "Finals", cls: "bg-fuchsia-100 text-fuchsia-800 border-fuchsia-200" },
  atp_1000: { label: "1000", cls: "bg-rose-100 text-rose-800 border-rose-200" },
  wta_1000: { label: "1000", cls: "bg-rose-100 text-rose-800 border-rose-200" },
  atp_500: { label: "500", cls: "bg-sky-100 text-sky-800 border-sky-200" },
  wta_500: { label: "500", cls: "bg-sky-100 text-sky-800 border-sky-200" },
  atp_250: { label: "250", cls: "bg-emerald-100 text-emerald-800 border-emerald-200" },
  wta_250: { label: "250", cls: "bg-emerald-100 text-emerald-800 border-emerald-200" },
  davis_cup: { label: "Davis", cls: "bg-indigo-100 text-indigo-800 border-indigo-200" },
  bjk_cup: { label: "BJK", cls: "bg-indigo-100 text-indigo-800 border-indigo-200" },
  challenger: { label: "Ch.", cls: "bg-ink-800 text-text-secondary border-ink-700" },
  itf: { label: "ITF", cls: "bg-ink-800 text-text-secondary border-ink-700" },
};

export function TournamentCard({
  t,
  dense = false,
  showPhase = false,
}: {
  t: IndexTournament;
  dense?: boolean;
  /** Render "(Qualifying)" alongside the name when t.phase is set.
   *  Opt-in because the tournaments listing intentionally hides it —
   *  only the live page surfaces phase. */
  showPhase?: boolean;
}) {
  const badge = CATEGORY_BADGE[t.category];
  const dateLine = formatRange(t.start_date, t.end_date);
  const { tour: preferred } = usePreferredTour();
  // Joint events: link to the user's preferred tour when both are available.
  const linkTour = pickTour(preferred, t.tours);

  return (
    <Link
      href={`/tournaments/${linkTour}/${t.slug}`}
      className="group flex items-center gap-3 rounded-md border border-ink-700 bg-ink-900 px-3 py-2.5 transition hover:border-ink-600 hover:bg-ink-800"
    >
      <Thumb imageUrl={t.image_url} fallback={flagEmoji(t.country_code)} />

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          {badge && (
            <span className={`inline-flex h-5 shrink-0 items-center rounded-full border px-1.5 text-[9px] font-bold uppercase tracking-wider ${badge.cls}`}>
              {badge.label}
            </span>
          )}
          <span className="truncate text-sm font-semibold">
            {t.name}
            {showPhase && t.phase === "qualifying" && (
              <span className="ml-1.5 text-text-muted font-medium">(Qualifying)</span>
            )}
          </span>
          <span className="shrink-0 text-[10px] font-bold uppercase tracking-wider text-text-muted">
            {(t.tours.length > 1 ? t.tours : [t.tour]).join(" · ")}
          </span>
        </div>
        {!dense && (
          <div className="mt-0.5 flex items-center gap-2 text-[11px] text-text-muted">
            {t.surface && <span className={surfaceColor(t.surface)}>{t.surface}</span>}
            {t.city && <span>{t.city}</span>}
            {dateLine && <span>· {dateLine}</span>}
          </div>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-2">
        {t.live_count > 0 ? (
          <span className="flex items-center gap-1.5">
            <LiveDot label={false} />
            <span className="text-xs font-semibold text-live tnum">{t.live_count}</span>
          </span>
        ) : t.today_count > 0 ? (
          <span className="text-[11px] font-semibold text-accent tnum">{t.today_count} today</span>
        ) : (
          <span className="text-[11px] text-text-muted">{t.year}</span>
        )}
      </div>
    </Link>
  );
}

function Thumb({ imageUrl, fallback }: { imageUrl: string | null; fallback: string }) {
  if (imageUrl) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={imageUrl}
        alt=""
        // contain, not cover: square crests (Wimbledon, AO, RG) fill the
        // box either way, but a wide horizontal logo (US Open) gets
        // cover-cropped to an unreadable slice ("ope"). Contain shows the
        // whole mark; the padding keeps it off the rounded corners.
        className="h-10 w-10 shrink-0 rounded-md border border-ink-700 bg-ink-800 object-contain p-0.5"
        loading="lazy"
      />
    );
  }
  return (
    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-ink-700 bg-ink-800 text-base">
      {fallback || "🎾"}
    </div>
  );
}

function formatRange(start: string | null, end: string | null): string {
  if (!start) return "";
  const s = new Date(start);
  if (!end || end === start) return s.toLocaleDateString([], { month: "short", day: "numeric" });
  const e = new Date(end);
  const sameMonth = s.getMonth() === e.getMonth();
  if (sameMonth) {
    return `${s.toLocaleDateString([], { month: "short", day: "numeric" })}–${e.getDate()}`;
  }
  return `${s.toLocaleDateString([], { month: "short", day: "numeric" })}–${e.toLocaleDateString([], { month: "short", day: "numeric" })}`;
}
