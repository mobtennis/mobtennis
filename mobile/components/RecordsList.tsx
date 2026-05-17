import { Link } from "expo-router";
import { Pressable, Text, View } from "react-native";

import { PlayerAvatar } from "@/components/PlayerAvatar";
import type { TournamentRecord } from "@/lib/api";
import { flagEmoji } from "@/lib/format";

export function RecordsList({ records }: { records: TournamentRecord[] }) {
  if (records.length === 0) return null;
  return (
    <View className="gap-2">
      {records.map((r) => (
        <RecordCard key={r.title} record={r} />
      ))}
    </View>
  );
}

function RecordCard({ record }: { record: TournamentRecord }) {
  const inner = (
    <View className="flex-row items-center gap-3 rounded-md border border-ink-700 bg-ink-900 px-3 py-2.5">
      {record.player_slug ? (
        <PlayerAvatar
          name={record.value}
          imageUrl={record.image_url}
          countryCode={record.country_code}
        />
      ) : record.country_code ? (
        <View className="h-8 w-8 items-center justify-center rounded-full bg-ink-700">
          <Text style={{ fontSize: 16 }}>{flagEmoji(record.country_code) || "🏳️"}</Text>
        </View>
      ) : null}
      <View className="min-w-0 flex-1">
        <Text className="text-[10px] font-bold uppercase tracking-wider text-text-muted">
          {record.title}
        </Text>
        <Text className="text-sm font-semibold text-text-primary" numberOfLines={1}>
          {record.value}
        </Text>
        {record.detail && (
          <Text className="text-[11px] text-text-muted">{record.detail}</Text>
        )}
      </View>
    </View>
  );
  if (record.player_slug) {
    return (
      <Link href={`/players/${record.player_slug}` as any} asChild>
        <Pressable>{inner}</Pressable>
      </Link>
    );
  }
  return inner;
}
