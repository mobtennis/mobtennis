import Link from "next/link";

/**
 * Renders a digest body paragraph, turning inline markdown links of
 * the form `[Display text](url)` into either <Link> (internal slugs)
 * or <a target="_blank"> (external news citations).
 *
 * The digest service produces these from two tightly scoped tables:
 * the internal LINKS list (player/tournament/H2H slugs) and the news
 * URLs offered the model this run. Backend sanitisation strips any
 * markdown link whose URL isn't on one of those allow-lists, so the
 * renderer doesn't need to validate URLs further — it just picks the
 * right anchor type based on whether the URL starts with `/` or
 * `http(s)`.
 *
 * No general markdown is supported: no bold, italics, lists, or
 * headers. Body is a single paragraph by design.
 */
export function DigestBody({ body }: { body: string }) {
  return (
    <p className="whitespace-pre-line text-[15px] leading-7 text-text-secondary">
      {renderInlineLinks(body)}
    </p>
  );
}

const LINK_RE = /\[([^\]]+)\]\(([^)]+)\)/g;
const LINK_CLASS =
  "text-accent underline decoration-dotted underline-offset-4 hover:text-accent-dim";

export function renderInlineLinks(body: string): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  let lastIndex = 0;
  let key = 0;
  for (const m of body.matchAll(LINK_RE)) {
    const idx = m.index ?? 0;
    if (idx > lastIndex) {
      out.push(<span key={key++}>{body.slice(lastIndex, idx)}</span>);
    }
    const text = m[1];
    const href = m[2];
    if (href.startsWith("/")) {
      // Internal link — Next.js client-side navigation.
      out.push(
        <Link key={key++} href={href} className={LINK_CLASS}>
          {text}
        </Link>,
      );
    } else if (href.startsWith("http://") || href.startsWith("https://")) {
      // External news citation — open in a new tab with noopener/noreferrer
      // so the publisher's page can't navigate ours and isn't fed our
      // referrer.
      out.push(
        <a
          key={key++}
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className={LINK_CLASS}
        >
          {text}
        </a>,
      );
    } else {
      // Unknown shape — strip the markdown but keep the text.
      out.push(<span key={key++}>{text}</span>);
    }
    lastIndex = idx + m[0].length;
  }
  if (lastIndex < body.length) {
    out.push(<span key={key++}>{body.slice(lastIndex)}</span>);
  }
  return out;
}

/** Plain-text view of the body, with markdown links collapsed to their
 * display text. Used in teasers, metadata descriptions, and anywhere
 * we need the prose without rendering `<a>` elements. */
export function stripMarkdownLinks(body: string): string {
  return body.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");
}
