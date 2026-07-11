import Link from "next/link";

import type { DigestImage } from "@/lib/api";

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
 *
 * Images (optional): a "lead" image renders above the prose; a "mid"
 * image is interleaved by splitting the paragraph at a sentence
 * boundary near its midpoint, so it reads like a proper news article.
 */
export function DigestBody({
  body,
  images = [],
}: {
  body: string;
  images?: DigestImage[];
}) {
  const lead = images.find((i) => i.anchor === "lead") ?? null;
  const mid = images.find((i) => i.anchor === "mid") ?? null;
  const [first, second] = mid ? splitForMid(body) : [body, ""];

  return (
    <>
      {lead && <Figure image={lead} />}
      <p className="whitespace-pre-line text-[15px] leading-7 text-text-secondary">
        {renderInlineLinks(first)}
      </p>
      {mid && (second ? (
        <>
          <Figure image={mid} />
          <p className="mt-4 whitespace-pre-line text-[15px] leading-7 text-text-secondary">
            {renderInlineLinks(second)}
          </p>
        </>
      ) : (
        // Couldn't find a clean split point — show it after the prose
        // rather than dropping it.
        <Figure image={mid} />
      ))}
    </>
  );
}

function Figure({ image }: { image: DigestImage }) {
  const hasCaption = Boolean(image.caption || image.credit);
  return (
    <figure className="my-4 overflow-hidden rounded-lg border border-ink-700 bg-ink-800">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={image.url}
        alt={image.caption ?? ""}
        className="max-h-[420px] w-full object-cover object-top"
        loading="lazy"
      />
      {hasCaption && (
        <figcaption className="px-3 py-2 text-[11px] leading-4 text-text-muted">
          {image.caption && (
            <span className="text-text-secondary">{image.caption}</span>
          )}
          {image.credit && (
            <>
              {image.caption ? " · " : ""}
              {image.credit_url ? (
                <a
                  href={image.credit_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline decoration-dotted underline-offset-2 hover:text-text-secondary"
                >
                  {image.credit}
                </a>
              ) : (
                image.credit
              )}
            </>
          )}
        </figcaption>
      )}
    </figure>
  );
}

/**
 * Split the body into two halves at the sentence boundary nearest the
 * midpoint, so a "mid" image sits between two runs of prose. Boundaries
 * inside a `[text](url)` markdown link are ignored so we never cut a
 * link in half. Returns ["", ""]-safe: falls back to [body, ""] when no
 * usable boundary exists (e.g. a single-sentence body).
 */
export function splitForMid(body: string): [string, string] {
  // Mask link spans so a period inside a URL/label isn't a split point.
  const linkRanges: Array<[number, number]> = [];
  for (const m of body.matchAll(LINK_RE)) {
    const idx = m.index ?? 0;
    linkRanges.push([idx, idx + m[0].length]);
  }
  const inLink = (i: number) => linkRanges.some(([a, b]) => i >= a && i < b);

  const mid = body.length / 2;
  let best = -1;
  const re = /[.!?]\s+/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(body)) !== null) {
    const cut = m.index + 1; // keep the punctuation with the first half
    if (inLink(m.index)) continue;
    if (best === -1 || Math.abs(cut - mid) < Math.abs(best - mid)) best = cut;
  }
  if (best === -1) return [body, ""];
  return [body.slice(0, best).trim(), body.slice(best).trim()];
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
