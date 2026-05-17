import Link from "next/link";

export function SectionHeader({
  title,
  subtitle,
  actionHref,
  actionLabel,
}: {
  title: string;
  subtitle?: string;
  actionHref?: string;
  actionLabel?: string;
}) {
  return (
    <div className="flex items-end justify-between px-1 pt-1">
      <div>
        <h2 className="text-base font-semibold tracking-tight">{title}</h2>
        {subtitle && <p className="text-xs text-text-muted">{subtitle}</p>}
      </div>
      {actionHref && (
        <Link href={actionHref} className="text-xs font-medium text-accent hover:text-accent-dim">
          {actionLabel ?? "See all"}
        </Link>
      )}
    </div>
  );
}
