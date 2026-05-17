// Relative path here is intentional — Metro does not apply tsconfig path
// aliases to runtime imports, so `@/global.css` silently misses and NativeWind
// never loads its style runtime, producing a totally white screen.
import "../global.css";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useEffect, useState } from "react";
import { GestureHandlerRootView } from "react-native-gesture-handler";

import { analytics } from "@/lib/analytics";
import { LiveStreamSubscriber } from "@/lib/live-stream";
import { registerForPushNotifications } from "@/lib/push";

export default function RootLayout() {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  useEffect(() => {
    // Best-effort: kick off push registration on launch. If permission isn't
    // granted, we'll re-prompt the next time the user tries to follow a match.
    void registerForPushNotifications();
    // Boot analytics once. Identifies the device token; queues events fired
    // before the token resolved.
    void analytics.init();
  }, []);

  return (
    <GestureHandlerRootView className="flex-1 bg-ink-950">
      <QueryClientProvider client={queryClient}>
        <LiveStreamSubscriber />
        <StatusBar style="dark" />
        <Stack
          screenOptions={{
            headerStyle: { backgroundColor: "#FAF7F0" },
            headerTitleStyle: { color: "#1F2A37", fontWeight: "700" },
            headerShadowVisible: false,
            contentStyle: { backgroundColor: "#FAF7F0" },
          }}
        >
          <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
          <Stack.Screen name="players/[slug]" options={{ title: "Player" }} />
          <Stack.Screen name="tournaments/[tour]/[slug]" options={{ title: "Tournament" }} />
          <Stack.Screen name="matches/[id]" options={{ title: "Match" }} />
          <Stack.Screen name="h2h/[matchup]" options={{ title: "Head-to-head" }} />
          <Stack.Screen name="following" options={{ title: "Following" }} />
          <Stack.Screen name="search" options={{ title: "Search" }} />
          <Stack.Screen name="credits" options={{ title: "Credits" }} />
        </Stack>
      </QueryClientProvider>
    </GestureHandlerRootView>
  );
}
