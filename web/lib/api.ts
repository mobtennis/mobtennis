// Server- and client-safe API client. Uses native fetch, no extra deps.
// Routes hit `/api/proxy/*` which is rewritten to the FastAPI backend
// in next.config.ts — same code path locally and in prod.

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type FetchOpts = RequestInit & { revalidate?: number | false };

// Hard cap any single request at 8s. Without this, an unreachable backend
// (e.g. during Vercel's build phase before the API is up) leaves fetch
// hanging on a TCP connect for the worker's full 60s timeout, after which
// Next gives up the whole page. With it, the .catch(() => default) paths
// in our pages actually fire and the build completes with empty data.
const REQUEST_TIMEOUT_MS = 8_000;

export async function api<T>(path: string, opts: FetchOpts = {}): Promise<T> {
  const { revalidate = 30, ...rest } = opts;
  const url = `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;

  const doFetch = async (): Promise<T> => {
    const res = await fetch(url, {
      ...rest,
      signal: rest.signal ?? AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      next: revalidate === false ? { revalidate: 0 } : { revalidate },
      headers: { Accept: "application/json", ...(rest.headers ?? {}) },
    });
    if (!res.ok) {
      throw new Error(`API ${res.status} ${res.statusText} — ${path}`);
    }
    return (await res.json()) as T;
  };

  // One retry on transient failures (timeouts, 5xx, connection-refused
  // during a backend restart). 250ms delay weathers the ~10s window
  // when systemd is bouncing uvicorn after a deploy: by the time the
  // second attempt fires, the new process is usually accepting again.
  // Without this, a single Vercel render unlucky enough to land mid-
  // restart cached an empty page for the whole revalidate window.
  try {
    return await doFetch();
  } catch {
    await new Promise((r) => setTimeout(r, 250));
    return await doFetch();
  }
}

// ----- Types ------------------------------------------------------------------

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
  | "scheduled"
  | "live"
  | "suspended"
  | "finished"
  | "retired"
  | "walkover"
  | "cancelled"
  | "postponed";

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

export type MatchBlurb = {
  kind: "preview" | "recap" | "";
  paragraph: string;
};

export type MatchDetail = MatchSummary & {
  started_at: string | null;
  finished_at: string | null;
  stats: MatchStats | null;
  blurb: MatchBlurb | null;
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

export type RankingRow = {
  rank: number;
  points: number | null;
  player: PlayerSummary;
};

export type RankingsResponse = {
  tour: string;
  week: string;
  rows: RankingRow[];
};

export type LiveRankingRow = RankingRow & {
  projected_rank: number;
  projected_points: number;
  points_change: number;
};

export type LiveRankingsResponse = {
  tour: string;
  week: string;
  rows: LiveRankingRow[];
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

/** Unified item used by FeedList — news + videos sorted by date. */
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

export type H2HMeeting = {
  year: number;
  tournament_name: string | null;
  tournament_slug: string | null;
  tournament_tour: string | null;
  round: string | null;
  winner_slug: string | null;
  score: string | null;
};

export type H2HSummary = {
  total_meetings: number;
  finals_meetings: number;
  span_years: number | null;
  first_meeting: H2HMeeting | null;
  last_meeting: H2HMeeting | null;
  current_streak_slug: string | null;
  current_streak_count: number;
};

export type H2HResponse = {
  player1: PlayerSummary;
  player2: PlayerSummary;
  p1_wins: number;
  p2_wins: number;
  matches: MatchSummary[];
  surface_splits: { surface: string; p1_wins: number; p2_wins: number }[];
  summary: H2HSummary | null;
};

export type SnapshotTitle = {
  year: number;
  tournament_slug: string;
  tournament_name: string;
  tournament_tour: string;
  category: string | null;
  surface: string | null;
  final_opponent_slug: string | null;
  final_opponent_name: string | null;
  final_score: string | null;
};

export type SurfaceRecord = {
  surface: string;
  wins: number;
  losses: number;
};

export type PlayerSnapshot = {
  slug: string;
  full_name: string;
  career_wins: number;
  career_losses: number;
  career_titles: number;
  career_finals: number;
  slam_titles: number;
  slam_finals: number;
  best_slam: SnapshotTitle | null;
  recent_wins: number;
  recent_losses: number;
  surfaces: SurfaceRecord[];
  best_surface: string | null;
  biggest_rival_slug: string | null;
  biggest_rival_name: string | null;
  biggest_rival_record_wins: number;
  biggest_rival_record_losses: number;
  recent_titles: SnapshotTitle[];
};

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

export type DigestSummary = {
  /** Monday of the ISO week the digest covers, e.g. "2026-05-11". */
  week_start: string;
  headline: string;
  generated_at: string;
};

export type NewsSource = {
  title: string;
  url: string;
  source: string;
};

export type DigestDetail = DigestSummary & {
  body_md: string;
  model_name: string;
  news_sources: NewsSource[];
};

export type CampaignBrief = {
  theme: string;
  rationale: string;
  keywords: string[];
  ad_headlines: string[];
  ad_descriptions: string[];
  landing_path: string;
};

export type CampaignBriefsResponse = {
  week_start: string;
  headline: string;
  generated_at: string;
  briefs: CampaignBrief[];
};

export type IndexSection = {
  key: string;
  title: string;
  tournaments: IndexTournament[];
  total: number;
};

export type TournamentsIndexResponse = {
  sections: IndexSection[];
};
