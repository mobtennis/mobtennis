import type { ReactNode } from "react";
import { RefreshControl, ScrollView, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

type Props = {
  children: ReactNode;
  // Loose return type so React Query's refetch() (Promise<QueryObserverResult>)
  // can be passed in without an arrow-wrap at every call site.
  onRefresh?: () => unknown;
  refreshing?: boolean;
  /** Fixed-height screens (no scroll) — Search uses this */
  fixed?: boolean;
};

export function Screen({ children, onRefresh, refreshing = false, fixed = false }: Props) {
  const insets = useSafeAreaInsets();
  if (fixed) {
    return <View className="flex-1 bg-ink-950 px-3" style={{ paddingTop: 8 }}>{children}</View>;
  }
  return (
    <ScrollView
      className="flex-1 bg-ink-950"
      contentContainerStyle={{ padding: 12, paddingBottom: 24 + insets.bottom, gap: 16 }}
      refreshControl={
        onRefresh ? (
          <RefreshControl refreshing={refreshing} onRefresh={() => { void onRefresh(); }} />
        ) : undefined
      }
    >
      {children}
    </ScrollView>
  );
}
