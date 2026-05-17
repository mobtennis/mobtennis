// Static-day-count countdown — server-rendered, no client tick. We're showing
// "starts in N days" not a live clock; simpler is fine.
export function Countdown({ targetDate }: { targetDate: string }) {
  const target = new Date(targetDate);
  const now = new Date();
  const diffMs = target.getTime() - now.getTime();
  const days = Math.ceil(diffMs / (1000 * 60 * 60 * 24));

  if (days <= 0) return null;

  return (
    <div className="rounded-lg border border-accent/30 bg-accent/10 p-4 text-center">
      <div className="text-[10px] font-bold uppercase tracking-wider text-accent">
        Starts in
      </div>
      <div className="mt-1 text-3xl font-bold tnum text-accent">
        {days} <span className="text-base font-semibold">{days === 1 ? "day" : "days"}</span>
      </div>
      <div className="mt-1 text-xs text-text-secondary">
        {target.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" })}
      </div>
    </div>
  );
}
