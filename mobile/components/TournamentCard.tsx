import { Link } from "expo-router";
import { Image, Pressable, Text, View } from "react-native";

import { LiveDot } from "@/components/LiveDot";
import type { IndexTournament } from "@/lib/api";
import { flagEmoji, surfaceColor } from "@/lib/format";
import { pickTour, usePreferredTour } from "@/lib/preferred-tour";

const CATEGORY_BADGE: Record<string, { label: string; bg: string; fg: string }> = {
  grand_slam: { label: "GS", bg: "bg-amber-100", fg: "text-amber-800" },
  atp_finals: { label: "Finals", bg: "bg-fuchsia-100", fg: "text-fuchsia-800" },
  wta_finals: { label: "Finals", bg: "bg-fuchsia-100", fg: "text-fuchsia-800" },
  atp_1000: { label: "1000", bg: "bg-rose-100", fg: "text-rose-800" },
  wta_1000: { label: "1000", bg: "bg-rose-100", fg: "text-rose-800" },
  atp_500: { label: "500", bg: "bg-sky-100", fg: "text-sky-800" },
  wta_500: { label: "500", bg: "bg-sky-100", fg: "text-sky-800" },
  atp_250: { label: "250", bg: "bg-emerald-100", fg: "text-emerald-800" },
  wta_250: { label: "250", bg: "bg-emerald-100", fg: "text-emerald-800" },
  davis_cup: { label: "Davis", bg: "bg-indigo-100", fg: "text-indigo-800" },
  bjk_cup: { label: "BJK", bg: "bg-indigo-100", fg: "text-indigo-800" },
  challenger: { label: "Ch.", bg: "bg-ink-800", fg: "text-text-secondary" },
  itf: { label: "ITF", bg: "bg-ink-800", fg: "text-text-secondary" },
};

export function TournamentCard({ t }: { t: IndexTournament }) {
  const badge = CATEGORY_BADGE[t.category];
  const dateLine = formatRange(t.start_date, t.end_date);
  const { tour: preferred } = usePreferredTour();
  const linkTour = pickTour(preferred, t.tours);

  return (
    <Link href={`/tournaments/${linkTour}/${t.slug}` as any} asChild>
      <Pressable className="flex-row items-center gap-3 rounded-md border border-ink-700 bg-ink-900 px-3 py-2.5">
        {t.image_url ? (
          <Image source={{ uri: t.image_url }} style={{ width: 40, height: 40, borderRadius: 8 }} />
        ) : (
          <View className="h-10 w-10 items-center justify-center rounded-md border border-ink-700 bg-ink-800">
            <Text style={{ fontSize: 18 }}>{flagEmoji(t.country_code) || "🎾"}</Text>
          </View>
        )}

        <View className="min-w-0 flex-1">
          <View className="flex-row items-center gap-2">
            {badge && (
              <View className={`rounded-full px-1.5 py-0.5 ${badge.bg}`}>
                <Text className={`text-[9px] font-bold uppercase tracking-wider ${badge.fg}`}>
                  {badge.label}
                </Text>
              </View>
            )}
            <Text className="flex-1 text-sm font-semibold text-text-primary" numberOfLines={1}>
              {t.name}
            </Text>
            <Text className="text-[10px] font-bold uppercase tracking-wider text-text-muted">
              {(t.tours.length > 1 ? t.tours : [t.tour]).join(" · ")}
            </Text>
          </View>
          <View className="mt-0.5 flex-row items-center gap-2">
            {t.surface && (
              <Text className={`text-[11px] ${surfaceColor(t.surface)}`}>{t.surface}</Text>
            )}
            {t.city && <Text className="text-[11px] text-text-muted">{t.city}</Text>}
            {dateLine && <Text className="text-[11px] text-text-muted">· {dateLine}</Text>}
          </View>
        </View>

        <View className="items-end">
          {t.live_count > 0 ? (
            <View className="flex-row items-center gap-1.5">
              <LiveDot label={false} />
              <Text className="text-xs font-semibold text-live">{t.live_count}</Text>
            </View>
          ) : t.today_count > 0 ? (
            <Text className="text-[11px] font-semibold text-accent">{t.today_count} today</Text>
          ) : (
            <Text className="text-[11px] text-text-muted">{t.year}</Text>
          )}
        </View>
      </Pressable>
    </Link>
  );
}

function formatRange(start: string | null, end: string | null): string {
  if (!start) return "";
  const s = new Date(start);
  if (!end || end === start) return s.toLocaleDateString([], { month: "short", day: "numeric" });
  const e = new Date(end);
  if (s.getMonth() === e.getMonth()) {
    return `${s.toLocaleDateString([], { month: "short", day: "numeric" })}–${e.getDate()}`;
  }
  return `${s.toLocaleDateString([], { month: "short", day: "numeric" })}–${e.toLocaleDateString([], { month: "short", day: "numeric" })}`;
}
