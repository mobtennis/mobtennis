"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";

// Mirrors the desktop TopBar exactly. Search stays a top-right icon in
// TopBar (also on mobile) so it's still one tap away.
const items = [
  { href: "/", label: "Live", icon: LiveIcon },
  { href: "/tournaments", label: "Tournaments", icon: TrophyIcon },
  { href: "/rankings/atp", label: "Rankings", icon: RankingsIcon },
  { href: "/news", label: "News", icon: NewsIcon },
  { href: "/following", label: "Get the app", icon: PhoneIcon, accent: true },
];

export function BottomNav() {
  const path = usePathname();
  return (
    <nav className="safe-pb fixed inset-x-0 bottom-0 z-40 border-t border-ink-700 bg-ink-950/95 backdrop-blur md:hidden">
      <ul className="grid grid-cols-5">
        {items.map(({ href, label, icon: Icon, accent }) => {
          const active = href === "/" ? path === "/" : path.startsWith(href);
          return (
            <li key={href}>
              <Link
                href={href}
                className={clsx(
                  "flex flex-col items-center gap-1 px-1 py-2.5 text-[10px] font-medium",
                  active
                    ? "text-accent"
                    : accent
                      ? "text-accent hover:text-accent-dim"
                      : "text-text-secondary hover:text-text-primary",
                )}
              >
                <Icon active={active} />
                <span className="truncate">{label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

const stroke = { fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

function LiveIcon({ active }: { active?: boolean }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" {...stroke}>
      <circle cx="12" cy="12" r="3" fill={active ? "currentColor" : "none"} />
      <path d="M5 12a7 7 0 0 1 14 0M2 12a10 10 0 0 1 20 0" />
    </svg>
  );
}
function TrophyIcon({ active }: { active?: boolean }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" {...stroke} fill={active ? "currentColor" : "none"}>
      <path d="M7 4h10v3a5 5 0 1 1-10 0V4z" />
      <path d="M7 6H4a3 3 0 0 0 3 3M17 6h3a3 3 0 0 1-3 3" />
      <path d="M9 14h6l-1 5h-4l-1-5z" />
      <path d="M8 21h8" />
    </svg>
  );
}
function NewsIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" {...stroke}>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M7 8h10M7 12h10M7 16h6" />
    </svg>
  );
}
function RankingsIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" {...stroke}>
      <path d="M4 20V10M12 20V4M20 20v-7" />
    </svg>
  );
}
function PhoneIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" {...stroke}>
      <rect x="6" y="3" width="12" height="18" rx="2" />
      <path d="M11 17h2" />
    </svg>
  );
}
