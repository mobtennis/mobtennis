import { Link } from "expo-router";
import { Pressable, Text } from "react-native";

/**
 * Renders a digest body paragraph, turning inline markdown links of
 * the form `[Display text](/path)` into expo-router Links wrapped in
 * Pressables.
 *
 * Mirrors web/components/DigestBody.tsx — same parser, RN primitives.
 */
export function DigestBody({ body }: { body: string }) {
  return (
    <Text className="text-[15px] leading-7 text-text-secondary">
      {renderInlineLinks(body)}
    </Text>
  );
}

const LINK_RE = /\[([^\]]+)\]\(([^)]+)\)/g;

function renderInlineLinks(body: string): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  let lastIndex = 0;
  let key = 0;
  for (const m of body.matchAll(LINK_RE)) {
    const idx = m.index ?? 0;
    if (idx > lastIndex) {
      out.push(<Text key={key++}>{body.slice(lastIndex, idx)}</Text>);
    }
    const text = m[1];
    const href = m[2];
    if (href.startsWith("/")) {
      out.push(
        <Link key={key++} href={href as any} asChild>
          <Pressable>
            {/* Inline pressable with underlined text — Expo Router's
                <Link> wraps a Pressable to make a child of a Text
                touchable while staying part of the paragraph flow. */}
            <Text className="text-accent underline">{text}</Text>
          </Pressable>
        </Link>,
      );
    } else {
      out.push(<Text key={key++}>{text}</Text>);
    }
    lastIndex = idx + m[0].length;
  }
  if (lastIndex < body.length) {
    out.push(<Text key={key++}>{body.slice(lastIndex)}</Text>);
  }
  return out;
}

/** Plain-text view with markdown links flattened to their display text.
 * Used in card teasers where the whole card is a single tap target. */
export function stripMarkdownLinks(body: string): string {
  return body.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");
}
