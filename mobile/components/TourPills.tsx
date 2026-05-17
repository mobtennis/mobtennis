import { Link } from "expo-router";
import { useEffect } from "react";
import { Pressable, Text, View } from "react-native";

import type { Tour } from "@/lib/api";
import { setPreferredTour } from "@/lib/preferred-tour";

type Props = {
  active: Tour;
  available: string[];
  slug: string;
};

export function TourPills({ active, available, slug }: Props) {
  // Landing on a tour-scoped detail page implies a preference.
  useEffect(() => {
    void setPreferredTour(active);
  }, [active]);

  if (available.length < 2) return null;

  return (
    <View className="mt-3 flex-row gap-1.5">
      {available.map((t) => {
        const isActive = t === active;
        return (
          <Link
            key={t}
            href={`/tournaments/${t}/${slug}` as any}
            asChild
          >
            <Pressable
              className={`rounded-full border px-2.5 py-0.5 ${
                isActive ? "border-accent bg-accent" : "border-ink-700 bg-ink-800"
              }`}
            >
              <Text
                className={`text-[11px] font-bold uppercase tracking-wider ${
                  isActive ? "text-white" : "text-text-secondary"
                }`}
              >
                {t}
              </Text>
            </Pressable>
          </Link>
        );
      })}
    </View>
  );
}
