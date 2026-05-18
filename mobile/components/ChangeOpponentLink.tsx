import { Link } from "expo-router";
import { Pressable, Text } from "react-native";

/**
 * "Change opponent" link under each player on the H2H card. Tap to
 * open the dedicated pick screen with this anchor pre-selected; the
 * picker tour-filters by `tourFilter` so an ATP anchor only matches
 * ATP opponents.
 */
export function ChangeOpponentLink({
  anchorSlug,
  tourFilter,
}: {
  anchorSlug: string;
  tourFilter?: string | null;
}) {
  const href = tourFilter
    ? `/h2h/pick?anchor=${anchorSlug}&tour=${tourFilter}`
    : `/h2h/pick?anchor=${anchorSlug}`;
  return (
    <Link href={href as any} asChild>
      <Pressable>
        <Text className="text-[10px] text-text-muted underline">
          change opponent
        </Text>
      </Pressable>
    </Link>
  );
}
