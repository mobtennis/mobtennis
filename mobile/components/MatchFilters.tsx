import { Pressable, ScrollView, Text, View } from "react-native";

import { analytics, EVENTS } from "@/lib/analytics";
import {
  ALL_CATEGORIES,
  CATEGORY_LABELS,
  type FilterScope,
  type MatchCategory,
  useMatchFilters,
} from "@/lib/match-filters";

type Props = {
  /** Categories to surface in this view. Defaults to all five. Tournament
   *  detail screens narrow this to the relevant tour. */
  visible?: readonly MatchCategory[];
  /** Logical scope used to track per-context lock state (so "clear all"
   *  on the ATP screen only locks the ATP scope). */
  scope?: FilterScope;
};

export function MatchFilterBar({ visible = ALL_CATEGORIES, scope }: Props) {
  const { effective, toggle, allVisibleOn, showAllVisible, clearVisible } =
    useMatchFilters({ visible, scope });

  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={{ paddingRight: 12 }}
      className="-mx-3"
    >
      <View className="flex-row items-center gap-2 px-3 py-1">
        {visible.map((cat) => {
          const on = effective.has(cat);
          return (
            <Pressable
              key={cat}
              onPress={() => {
                analytics.track(EVENTS.filterToggled, {
                  category: cat,
                  action: on ? "off" : "on",
                  scope: scope ?? "all",
                });
                toggle(cat);
              }}
              className={`rounded-full border px-3 py-1.5 ${
                on ? "border-accent bg-accent/10" : "border-ink-700 bg-ink-900"
              }`}
            >
              <Text
                className={`text-xs font-semibold ${
                  on ? "text-accent" : "text-text-muted"
                }`}
              >
                {CATEGORY_LABELS[cat]}
              </Text>
            </Pressable>
          );
        })}
        <Pressable
          onPress={allVisibleOn ? clearVisible : showAllVisible}
          className="px-2 py-1"
        >
          <Text className="text-[11px] text-text-muted underline">
            {allVisibleOn ? "clear all" : "show all"}
          </Text>
        </Pressable>
      </View>
    </ScrollView>
  );
}
