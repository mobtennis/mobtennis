import { useEffect, useRef } from "react";
import { Animated, Text, View } from "react-native";

// Two layered animations to match the web LiveDot:
//   • outer ring scales 1 → 2 with opacity 1 → 0, looping (broadcast ping)
//   • text fades opacity 1 ↔ 0.5, looping (subtle breathing)
// Both share the same useNativeDriver=true so they're cheap.
export function LiveDot({ label = true }: { label?: boolean }) {
  const ping = useRef(new Animated.Value(0)).current;
  const pulse = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    const pingLoop = Animated.loop(
      Animated.timing(ping, { toValue: 1, duration: 1400, useNativeDriver: true }),
    );
    const pulseLoop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 0.5, duration: 700, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 1, duration: 700, useNativeDriver: true }),
      ]),
    );
    pingLoop.start();
    pulseLoop.start();
    return () => {
      pingLoop.stop();
      pulseLoop.stop();
    };
  }, [ping, pulse]);

  return (
    <View className="flex-row items-center gap-1.5">
      <View style={{ width: 8, height: 8 }}>
        <Animated.View
          className="absolute h-2 w-2 rounded-full bg-live"
          style={{
            opacity: ping.interpolate({ inputRange: [0, 1], outputRange: [0.75, 0] }),
            transform: [{ scale: ping.interpolate({ inputRange: [0, 1], outputRange: [1, 2] }) }],
          }}
        />
        <View className="absolute h-2 w-2 rounded-full bg-live" />
      </View>
      {label && (
        <Animated.Text
          style={{ opacity: pulse }}
          className="text-[10px] font-bold uppercase tracking-wider text-live"
        >
          LIVE
        </Animated.Text>
      )}
    </View>
  );
}

/** Static amber dot for matches that were live but are currently
 * paused (rain delay etc.). No animation — reads as "paused" rather
 * than "broadcasting right now." */
export function SuspendedDot({ label = true }: { label?: boolean }) {
  return (
    <View className="flex-row items-center gap-1.5">
      <View className="h-2 w-2 rounded-full" style={{ backgroundColor: "#fbbf24" }} />
      {label && (
        <Text className="text-[10px] font-bold uppercase tracking-wider" style={{ color: "#fbbf24" }}>
          SUSPENDED
        </Text>
      )}
    </View>
  );
}
