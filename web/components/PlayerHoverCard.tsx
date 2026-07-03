"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import type { PlayerDetail } from "@/lib/api";
import { flagEmoji } from "@/lib/format";

/**
 * Wikipedia-style hover preview for a player. Wraps any child
 * element (typically a player name in a match card row). On
 * hover — with a small delay so cursor drift doesn't trigger it —
 * fetches PlayerDetail and pops a card with the big image + core
 * facts + a link to the full profile.
 *
 * Mobile: touch devices report (hover: none) — we skip the wrapper
 * entirely there. Player names remain plain text; the match card's
 * native Link still navigates on tap. If we want a mobile
 * equivalent later, long-press → sheet is the shape.
 *
 * Fetch cache is module-scoped so hovering the same name across
 * multiple cards reuses the response and switching back is
 * instant.
 */

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "https://api.mob.tennis";

const cache = new Map<string, PlayerDetail>();
const inFlight = new Map<string, Promise<PlayerDetail>>();


function fetchPlayer(slug: string): Promise<PlayerDetail> {
  const cached = cache.get(slug);
  if (cached) return Promise.resolve(cached);
  const pending = inFlight.get(slug);
  if (pending) return pending;
  const p = fetch(`${API_BASE}/api/players/${encodeURIComponent(slug)}`)
    .then((r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json() as Promise<PlayerDetail>;
    })
    .then((d) => {
      cache.set(slug, d);
      inFlight.delete(slug);
      return d;
    })
    .catch((e) => {
      inFlight.delete(slug);
      throw e;
    });
  inFlight.set(slug, p);
  return p;
}


function useCanHover(): boolean {
  const [can, setCan] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined") return;
    const m = window.matchMedia("(hover: hover) and (pointer: fine)");
    setCan(m.matches);
    const listener = (e: MediaQueryListEvent) => setCan(e.matches);
    m.addEventListener("change", listener);
    return () => m.removeEventListener("change", listener);
  }, []);
  return can;
}


function ageFromBirth(birth: string | null): number | null {
  if (!birth) return null;
  const d = new Date(birth);
  if (Number.isNaN(d.getTime())) return null;
  const now = new Date();
  let age = now.getFullYear() - d.getFullYear();
  const m = now.getMonth() - d.getMonth();
  if (m < 0 || (m === 0 && now.getDate() < d.getDate())) age -= 1;
  return age;
}


type PopoverPos = {
  top: number;
  left: number;
  width: number;
};


const POPOVER_W = 300;
const HOVER_OPEN_DELAY = 250;
const HOVER_CLOSE_DELAY = 120;


export function PlayerHoverCard({
  slug,
  children,
}: {
  slug: string | null | undefined;
  children: React.ReactNode;
}) {
  const canHover = useCanHover();
  const triggerRef = useRef<HTMLSpanElement | null>(null);
  const openTimer = useRef<number | null>(null);
  const closeTimer = useRef<number | null>(null);
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<PopoverPos | null>(null);
  const [data, setData] = useState<PlayerDetail | null>(null);

  useEffect(() => {
    return () => {
      if (openTimer.current) window.clearTimeout(openTimer.current);
      if (closeTimer.current) window.clearTimeout(closeTimer.current);
    };
  }, []);

  if (!canHover || !slug) return <>{children}</>;

  const positionFromTrigger = (): PopoverPos | null => {
    const el = triggerRef.current;
    if (!el) return null;
    const rect = el.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    // Prefer below; flip to above if the card would run past the
    // viewport bottom (assume 260px card height as a rough cap for
    // the flip decision — actual height is content-driven).
    const spaceBelow = vh - rect.bottom;
    const flipAbove = spaceBelow < 260 && rect.top > 260;
    const top = flipAbove ? rect.top - 8 - 260 : rect.bottom + 8;
    const left = Math.max(8, Math.min(rect.left, vw - POPOVER_W - 8));
    return { top, left, width: POPOVER_W };
  };

  const show = () => {
    if (closeTimer.current) {
      window.clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
    if (openTimer.current) return;
    openTimer.current = window.setTimeout(async () => {
      openTimer.current = null;
      setPos(positionFromTrigger());
      setOpen(true);
      // Prefer cache first (instant), else fetch.
      const cached = cache.get(slug);
      if (cached) {
        setData(cached);
        return;
      }
      try {
        const d = await fetchPlayer(slug);
        setData(d);
      } catch {
        /* leave loading state visible; blip on next open */
      }
    }, HOVER_OPEN_DELAY);
  };

  const hide = () => {
    if (openTimer.current) {
      window.clearTimeout(openTimer.current);
      openTimer.current = null;
    }
    closeTimer.current = window.setTimeout(() => {
      closeTimer.current = null;
      setOpen(false);
    }, HOVER_CLOSE_DELAY);
  };

  return (
    <>
      <span
        ref={triggerRef}
        onMouseEnter={show}
        onMouseLeave={hide}
        className="inline"
      >
        {children}
      </span>
      {open && pos && typeof document !== "undefined" &&
        createPortal(
          <div
            style={{
              position: "fixed",
              top: pos.top,
              left: pos.left,
              width: pos.width,
              zIndex: 50,
            }}
            onMouseEnter={show}
            onMouseLeave={hide}
            // Don't let clicks inside the popover bubble to the
            // wrapping match-card Link (which would navigate away).
            onClick={(e) => e.stopPropagation()}
            className="overflow-hidden rounded-lg border border-ink-700 bg-ink-900 shadow-card"
            role="dialog"
          >
            <PopoverBody player={data} slug={slug} />
          </div>,
          document.body,
        )}
    </>
  );
}


function PopoverBody({ player, slug }: { player: PlayerDetail | null; slug: string }) {
  if (!player) {
    return (
      <div className="flex h-40 items-center justify-center text-xs text-text-muted">
        Loading…
      </div>
    );
  }
  const hero = player.hero_image_url || player.image_url;
  const flag = flagEmoji(player.country_code);
  const age = ageFromBirth(player.birth_date);
  return (
    <div className="text-sm">
      {hero ? (
        <div className="aspect-[4/3] w-full overflow-hidden bg-ink-800">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={hero}
            alt={player.full_name}
            className="h-full w-full object-cover"
            loading="lazy"
          />
        </div>
      ) : null}
      <div className="p-3 space-y-2">
        <div>
          <div className="text-base font-bold text-text-primary">
            {flag && <span className="mr-1.5">{flag}</span>}
            {player.full_name}
          </div>
          <div className="text-[11px] uppercase tracking-wider text-text-muted">
            {player.tour.toUpperCase()}
            {age !== null && <span> · Age {age}</span>}
            {player.plays && <span> · {player.plays}</span>}
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <Stat
            label="Rank"
            value={player.current_rank !== null ? `#${player.current_rank}` : "–"}
          />
          <Stat
            label="Career high"
            value={player.career_high_rank !== null ? `#${player.career_high_rank}` : "–"}
          />
        </div>
        {player.bio && (
          <p className="line-clamp-3 text-xs text-text-secondary">
            {player.bio}
          </p>
        )}
        <a
          href={`/players/${slug}`}
          className="block text-xs font-semibold text-accent hover:text-accent-dim"
        >
          Full profile →
        </a>
      </div>
    </div>
  );
}


function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-ink-700 bg-ink-800 px-2 py-1">
      <div className="text-[10px] uppercase tracking-wider text-text-muted">
        {label}
      </div>
      <div className="text-sm font-bold tabular-nums text-text-primary">
        {value}
      </div>
    </div>
  );
}
