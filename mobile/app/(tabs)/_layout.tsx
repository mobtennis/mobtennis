import { Link, Tabs } from "expo-router";
import { Pressable } from "react-native";
import Svg, { Circle, Path, Polygon } from "react-native-svg";

const ACCENT = "#16A34A";
const TEXT_SECONDARY = "#5C6473";
const TEXT_PRIMARY = "#1F2A37";

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: ACCENT,
        tabBarInactiveTintColor: TEXT_SECONDARY,
        tabBarStyle: {
          backgroundColor: "#FFFFFF",
          borderTopColor: "#E5DDC8",
          height: 84,
          paddingTop: 6,
        },
        tabBarLabelStyle: { fontSize: 10, fontWeight: "600" },
        headerStyle: { backgroundColor: "#FAF7F0" },
        headerTitleStyle: { color: TEXT_PRIMARY, fontWeight: "700" },
        headerShadowVisible: false,
        // Search + Following live as header icons on every tab so they're
        // one tap away without taking a precious bottom-tab slot.
        headerLeft: () => (
          <Link href="/search" asChild>
            <Pressable style={{ marginLeft: 12, height: 36, width: 36, alignItems: "center", justifyContent: "center" }}>
              <SearchIcon color={TEXT_PRIMARY} />
            </Pressable>
          </Link>
        ),
        headerRight: () => (
          <Link href="/following" asChild>
            <Pressable style={{ marginRight: 12, height: 36, width: 36, alignItems: "center", justifyContent: "center" }}>
              <StarIcon color={TEXT_PRIMARY} />
            </Pressable>
          </Link>
        ),
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "Live",
          headerTitle: "Mob Tennis",
          tabBarIcon: ({ color }) => <LiveIcon color={color} />,
        }}
      />
      <Tabs.Screen
        name="tournaments"
        options={{
          title: "Tournaments",
          tabBarIcon: ({ color }) => <TrophyIcon color={color} />,
        }}
      />
      <Tabs.Screen
        name="rankings"
        options={{
          title: "Rankings",
          tabBarIcon: ({ color }) => <RankingsIcon color={color} />,
        }}
      />
      <Tabs.Screen
        name="news"
        options={{
          title: "News",
          tabBarIcon: ({ color }) => <NewsIcon color={color} />,
        }}
      />
    </Tabs>
  );
}

const ICON = 22;

function LiveIcon({ color }: { color: string }) {
  return (
    <Svg width={ICON} height={ICON} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <Circle cx={12} cy={12} r={3} fill={color} />
      <Path d="M5 12a7 7 0 0 1 14 0M2 12a10 10 0 0 1 20 0" />
    </Svg>
  );
}
function TrophyIcon({ color }: { color: string }) {
  return (
    <Svg width={ICON} height={ICON} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <Path d="M7 4h10v3a5 5 0 1 1-10 0V4z" />
      <Path d="M7 6H4a3 3 0 0 0 3 3M17 6h3a3 3 0 0 1-3 3" />
      <Path d="M9 14h6l-1 5h-4l-1-5z" />
      <Path d="M8 21h8" />
    </Svg>
  );
}
function RankingsIcon({ color }: { color: string }) {
  return (
    <Svg width={ICON} height={ICON} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <Path d="M4 20V13M10 20V8M16 20V4M22 20H2" />
    </Svg>
  );
}
function NewsIcon({ color }: { color: string }) {
  return (
    <Svg width={ICON} height={ICON} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <Path d="M3 4h14a2 2 0 0 1 2 2v12H3z" />
      <Path d="M19 8h2v8a2 2 0 0 1-2 2" />
      <Path d="M7 8h7M7 12h7M7 16h4" />
    </Svg>
  );
}
function SearchIcon({ color }: { color: string }) {
  return (
    <Svg width={20} height={20} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <Circle cx={11} cy={11} r={7} />
      <Path d="M21 21l-4.3-4.3" />
    </Svg>
  );
}
function StarIcon({ color }: { color: string }) {
  return (
    <Svg width={20} height={20} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <Polygon points="12,2 15,9 22,9.5 17,14.5 18.5,22 12,18 5.5,22 7,14.5 2,9.5 9,9" />
    </Svg>
  );
}
