import { Linking, Pressable, Text, View } from "react-native";

import { Screen } from "@/components/Screen";

export default function CreditsScreen() {
  return (
    <Screen>
      <View className="space-y-4 px-1">
        <Text className="text-2xl font-bold text-text-primary">Credits & data sources</Text>
        <Text className="text-sm text-text-secondary">
          Mob Tennis stands on the shoulders of a few generous data sets.
        </Text>

        <Section title="Historical player & match data">
          <Text className="text-sm text-text-secondary">
            Player biographies, historical match records, and tournament
            metadata are derived from Jeff Sackmann's
            <Link url="https://github.com/JeffSackmann/tennis_atp" label=" tennis_atp" />
            {" "}and
            <Link url="https://github.com/JeffSackmann/tennis_wta" label=" tennis_wta" />
            {" "}datasets, distributed under the
            <Link url="https://creativecommons.org/licenses/by-nc-sa/4.0/" label=" CC BY-NC-SA 4.0" />
            {" "}license. We're enormously grateful — it's the closest thing
            tennis has to a community-maintained record.
          </Text>
        </Section>

        <Section title="Live scores & fixtures">
          <Text className="text-sm text-text-secondary">
            Live match data is licensed from
            <Link url="https://api-tennis.com/" label=" api-tennis.com" />.
          </Text>
        </Section>

        <Section title="Bracket structure & seeds">
          <Text className="text-sm text-text-secondary">
            Draw structure and seed information for top-tier events (Grand
            Slams, ATP/WTA 1000) is sourced from the corresponding English
            Wikipedia tournament-draw pages, made available under the
            <Link url="https://creativecommons.org/licenses/by-sa/4.0/" label=" CC BY-SA 4.0" />
            {" "}license.
          </Text>
        </Section>

        <Section title="News">
          <Text className="text-sm text-text-secondary">
            News headlines and links are aggregated from the public RSS feeds
            of the respective publications. Each item links back to the
            original source. We don't host article text — only titles, summaries
            and attribution.
          </Text>
        </Section>

        <Section title="Player photos & flags">
          <Text className="text-sm text-text-secondary">
            Player photographs are provided by api-tennis. Country flags are
            the standard Unicode regional-indicator emoji rendered by your
            device.
          </Text>
        </Section>
      </View>
    </Screen>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View className="gap-2">
      <Text className="text-base font-semibold text-text-primary">{title}</Text>
      {children}
    </View>
  );
}

function Link({ url, label }: { url: string; label: string }) {
  return (
    <Pressable onPress={() => Linking.openURL(url)}>
      <Text className="text-accent underline">{label}</Text>
    </Pressable>
  );
}
