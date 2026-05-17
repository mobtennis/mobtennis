import Constants from "expo-constants";

import { getDeviceToken } from "@/lib/device";

// Resolution order:
//   1. EXPO_PUBLIC_API_BASE_URL — for `EXPO_PUBLIC_API_BASE_URL=... expo start` (dev override)
//   2. app.json extra.apiBaseUrl — the baked-in default (prod URL)
//   3. localhost — last-resort fallback
export const API_BASE: string =
  process.env.EXPO_PUBLIC_API_BASE_URL ??
  (Constants.expoConfig?.extra?.apiBaseUrl as string | undefined) ??
  "http://localhost:8000";

type FetchOpts = RequestInit & { authed?: boolean };

export async function api<T>(path: string, opts: FetchOpts = {}): Promise<T> {
  const { authed = false, headers, ...rest } = opts;
  const url = `${API_BASE.replace(/\/$/, "")}${path.startsWith("/") ? path : `/${path}`}`;

  const finalHeaders: Record<string, string> = {
    Accept: "application/json",
    ...(headers as Record<string, string>),
  };
  if (authed) {
    finalHeaders["X-User-Token"] = await getDeviceToken();
  }

  const start = Date.now();
  if (__DEV__) console.log(`[api] → ${url}`);
  try {
    const res = await fetch(url, { ...rest, headers: finalHeaders });
    if (__DEV__) console.log(`[api] ← ${res.status} ${url} (${Date.now() - start}ms)`);
    if (!res.ok) {
      throw new Error(`API ${res.status} ${res.statusText} — ${path}`);
    }
    return (await res.json()) as T;
  } catch (e) {
    if (__DEV__) console.log(`[api] ✗ ${url} (${Date.now() - start}ms):`, e);
    throw e;
  }
}

// ----- Types (mirror of web/lib/api.ts; keep in sync) ------------------------

export type Tour = "atp" | "wta";

export type PlayerSummary = {
  slug: string;
  full_name: string;
  tour: Tour;
  country_code: string | null;
  current_rank: number | null;
  image_url: string | null;
};

export type PlayerDetail = PlayerSummary & {
  first_name: string | null;
  last_name: string | null;
  birth_date: string | null;
  height_cm: number | null;
  plays: string | null;
  turned_pro: number | null;
  career_high_rank: number | null;
  bio: string | null;
  wikipedia_url: string | null;
  instagram_handle: string | null;
  twitter_handle: string | null;
  instagram_latest_post_url: string | null;
};

export type MatchStatus =
  | "scheduled" | "live" | "suspended" | "finished" | "retired" | "walkover" | "cancelled" | "postponed";

export type PlayerStats = {
  service_games_won: number;
  service_games_played: number;
  break_points_won: number;
  break_points_total: number;
  points_won: number;
};

export type MatchStats = {
  player1: PlayerStats;
  player2: PlayerStats;
};

export type MatchDetail = MatchSummary & {
  started_at: string | null;
  finished_at: string | null;
  stats: MatchStats | null;
};

export type MatchSummary = {
  id: number;
  tournament_slug: string;
  tournament_year: number;
  tournament_name: string;
  tournament_tour: Tour | null;
  tournament_category: string | null;
  tournament_surface: string | null;
  round: string | null;
  court: string | null;
  scheduled_at: string | null;
  status: MatchStatus;
  player1: PlayerSummary | null;
  player2: PlayerSummary | null;
  score: string | null;
  current_set: number | null;
  current_game: string | null;
  server_player_id: number | null;
  server_slot: 1 | 2 | null;
  winner_id: number | null;
  winner_slot: 1 | 2 | null;
  is_doubles: boolean;
  best_of: number;
  api_tennis_id: string | null;
  bracket_position: number | null;
  player1_seed: number | null;
  player2_seed: number | null;
};

export type TournamentSummary = {
  slug: string;
  year: number;
  name: string;
  tour: Tour;
  category: string;
  surface: string | null;
  indoor: boolean;
  city: string | null;
  country_code: string | null;
  start_date: string | null;
  end_date: string | null;
  draw_size: number | null;
  image_url: string | null;
};

export type TournamentDetail = TournamentSummary & {
  prize_money: number | null;
  description: string | null;
  wikipedia_url: string | null;
  available_tours: string[];
};

export type IndexTournament = {
  slug: string;
  year: number;
  name: string;
  tour: Tour;
  category: string;
  surface: string | null;
  city: string | null;
  country_code: string | null;
  start_date: string | null;
  end_date: string | null;
  image_url: string | null;
  live_count: number;
  today_count: number;
  is_in_progress: boolean;
  tours: string[];
};

export type TournamentsIndexSection = {
  key: string;
  title: string;
  tournaments: IndexTournament[];
  total: number;
};

export type TournamentsIndexResponse = {
  sections: TournamentsIndexSection[];
};

export type RankingsResponse = {
  tour: string;
  week: string;
  rows: { rank: number; points: number | null; player: PlayerSummary }[];
};

export type NewsItemSummary = {
  id: number;
  source: string;
  source_url: string;
  title: string;
  summary: string | null;
  image_url: string | null;
  author: string | null;
  published_at: string;
  player_slugs: string[];
  tournament_slugs: string[];
};

export type VideoItemSummary = {
  id: number;
  source: string;
  video_id: string;
  title: string;
  summary: string | null;
  thumbnail_url: string | null;
  channel_name: string | null;
  published_at: string;
  player_slugs: string[];
  tournament_slugs: string[];
  match_id: number | null;
  is_portrait: boolean | null;
};

export type FeedItem =
  | { kind: "news"; item: NewsItemSummary }
  | { kind: "video"; item: VideoItemSummary };

export function mergeFeed(
  news: NewsItemSummary[],
  videos: VideoItemSummary[],
): FeedItem[] {
  const all: FeedItem[] = [
    ...news.map((n): FeedItem => ({ kind: "news", item: n })),
    ...videos.map((v): FeedItem => ({ kind: "video", item: v })),
  ];
  all.sort((a, b) => +new Date(b.item.published_at) - +new Date(a.item.published_at));
  return all;
}

export type TournamentHistoryEntry = {
  tournament_slug: string;
  tournament_year: number;
  tournament_name: string;
  tournament_tour: Tour;
  tournament_category: string | null;
  tournament_surface: string | null;
  tournament_image_url: string | null;
  start_date: string | null;
  end_date: string | null;
  result: string;
  is_winner: boolean;
};

export type TournamentChampion = {
  year: number;
  champion: PlayerSummary;
};

export type LastEdition = {
  year: number;
  champion: PlayerSummary;
  runner_up: PlayerSummary | null;
  final_score: string | null;
};

export type TournamentRecord = {
  title: string;
  value: string;
  detail: string | null;
  player_slug: string | null;
  image_url: string | null;
  country_code: string | null;
};

export type TournamentStats = {
  first_held: number | null;
  total_editions: number;
  typical_month: number | null;
  draw_size: number | null;
  prize_money: number | null;
  surface: string | null;
  indoor: boolean;
};

export type TournamentOverview = {
  last_edition: LastEdition | null;
  records: TournamentRecord[];
  stats: TournamentStats;
};

export type SearchHit = {
  kind: "player" | "tournament";
  slug: string;
  name: string;
  tour: string | null;
  year: number | null;
  country_code: string | null;
  rank: number | null;
};

export type FollowKind = "player" | "tournament";
export type Follow = {
  kind: FollowKind;
  target_slug: string;
  target_tour: Tour | null;
};

export type MatchFollowGranularity = "key_moments" | "every_game";
export type MatchFollow = {
  match_id: number;
  granularity: MatchFollowGranularity;
};
