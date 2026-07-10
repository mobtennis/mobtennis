/**
 * Renders a schema.org JSON-LD block. Structured data is what earns the
 * sports rich results / knowledge-panel treatment in Google (SportsEvent
 * match cards, athlete Person cards) — plain metadata doesn't.
 *
 * Server component: the <script> is in the SSR HTML, which is what
 * crawlers read. `data` is a plain object; we stringify it ourselves so
 * the payload is inert (no JSX children, no hydration).
 */
export function JsonLd({ data }: { data: Record<string, unknown> }) {
  return (
    <script
      type="application/ld+json"
      // eslint-disable-next-line react/no-danger -- inert, server-rendered JSON
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }}
    />
  );
}
