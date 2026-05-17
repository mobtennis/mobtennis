import type { NewsItemSummary } from "@/lib/api";
import { formatRelative } from "@/lib/format";

export function NewsList({ items, compact = false }: { items: NewsItemSummary[]; compact?: boolean }) {
  if (items.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-ink-700 px-4 py-8 text-center text-text-muted">
        No news yet.
      </div>
    );
  }
  return (
    <ul className="space-y-2">
      {items.map((item) => (
        <li key={item.id}>
          <a
            href={item.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex gap-3 rounded-md border border-ink-700 bg-ink-900 p-3 transition hover:border-ink-600 hover:bg-ink-800"
          >
            {item.image_url && !compact && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={item.image_url} alt="" className="h-20 w-20 shrink-0 rounded-md object-cover" />
            )}
            <div className="min-w-0 flex-1">
              <h3 className="line-clamp-2 text-sm font-semibold leading-snug">{item.title}</h3>
              {item.summary && !compact && (
                <p className="mt-1 line-clamp-2 text-xs leading-snug text-text-secondary">
                  {item.summary}
                </p>
              )}
              <div className="mt-1 flex items-center gap-2 text-[11px] text-text-muted">
                <span className="font-medium uppercase tracking-wider">{item.source}</span>
                <span>·</span>
                <time dateTime={item.published_at}>{formatRelative(item.published_at)}</time>
              </div>
            </div>
          </a>
        </li>
      ))}
    </ul>
  );
}
