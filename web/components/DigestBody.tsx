import Link from "next/link";

/**
 * Renders a digest body paragraph, turning inline markdown links of
 * the form `[Display text](/path)` into <Link> elements.
 *
 * The digest service produces these from a tightly scoped LINKS table
 * (only known player / tournament / H2H slugs), and the model is
 * forbidden from inventing URLs — but we still defensively require
 * internal `/` prefixes here so a hypothetical prompt-injection
 * couldn't sneak in an external URL.
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
    // Only internal links. Anything else falls through as plain text —
    // strips the markdown but doesn't expose the URL.
    if (href.startsWith("/")) {
      out.push(
        <Link
          key={key++}
          href={href}
          className="text-accent underline decoration-dotted underline-offset-4 hover:text-accent-dim"
        >
          {text}
        </Link>,
      );
    } else {
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
