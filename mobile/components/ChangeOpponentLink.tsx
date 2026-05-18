import { useState } from "react";
import { Pressable, Text, View } from "react-native";

import { OpponentPicker } from "@/components/OpponentPicker";

/**
 * "Change opponent" toggle for the mobile H2H card. Tap → reveal an
 * inline picker; tapping a player navigates to the new H2H URL.
 */
export function ChangeOpponentLink({
  anchorSlug,
  tourFilter,
}: {
  anchorSlug: string;
  tourFilter?: string | null;
}) {
  const [open, setOpen] = useState(false);
  if (open) {
    return (
      <View className="w-full gap-1">
        <OpponentPicker anchorSlug={anchorSlug} tourFilter={tourFilter} />
        <Pressable onPress={() => setOpen(false)}>
          <Text className="text-center text-[10px] text-text-muted underline">
            cancel
          </Text>
        </Pressable>
      </View>
    );
  }
  return (
    <Pressable onPress={() => setOpen(true)}>
      <Text className="text-[10px] text-text-muted underline">
        change opponent
      </Text>
    </Pressable>
  );
}
