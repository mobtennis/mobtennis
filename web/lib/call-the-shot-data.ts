/**
 * Hand-typed Call the Shot prototype items.
 *
 * To swap in a real clip: find a tennis highlight on YouTube, scrub
 * to a rally just BEFORE the winning shot strike, note the
 * timestamp (seconds, fractional is fine), and the 4 options.
 *
 * `correct_index` is 0-based into `options`.
 *
 * Keeping data in a TS file rather than a DB while we feel out
 * whether the UX lands. If it does, move to a backend model +
 * admin builder, same shape as Spot the Ball.
 */

export type CallTheShotItem = {
  id: string;
  /** YouTube video ID, e.g. "dQw4w9WgXcQ" — NOT the full URL. */
  video_id: string;
  /** Where to start the clip, in seconds. Lets us skip past intro
   *  cards and dead air before the rally we care about. Defaults to 0
   *  if omitted. */
  start_at_s?: number;
  /** Where to pause, in seconds. Fractional ok — YouTube's seekTo
   *  accepts sub-second precision. */
  pause_at_s: number;
  /** One-line context shown under the video. */
  caption: string;
  /** 4 prediction buttons. Index 0..3 — correct_index points at the right one. */
  options: [string, string, string, string];
  correct_index: 0 | 1 | 2 | 3;
  /** Optional attribution / link out, shown small under the video. */
  source_url?: string;
};

export const CALL_THE_SHOT_ITEMS: CallTheShotItem[] = [
  // Real Wimbledon 2025 highlights from the official Wimbledon channel.
  // Pause timestamps and correct_index are FIRST PASS — needs the
  // operator to scrub each video, find a rally just before a winning
  // shot, and adjust pause_at_s + correct_index. The video_id and
  // caption are correct.
  {
    id: "wim-2025-men-final-1",
    video_id: "eRbTHj2KLro",
    start_at_s: 15,
    pause_at_s: 27.5,
    caption: "Sinner vs Alcaraz · Wimbledon 2025 final",
    options: [
      "Crosscourt volley",
      "Volley down the line",
      "Lob down the line",
      "Body shot",
    ],
    correct_index: 0,
    source_url: "https://www.youtube.com/watch?v=eRbTHj2KLro",
  },
  {
    id: "wim-2025-men-final-2",
    video_id: "eRbTHj2KLro",
    start_at_s: 35,
    pause_at_s: 44,
    caption: "Sinner vs Alcaraz · Wimbledon 2025 final",
    options: [
      "Crosscourt drop shot",
      "Volley crosscourt",
      "Volley down the line",
      "Body shot",
    ],
    correct_index: 0,
    source_url: "https://www.youtube.com/watch?v=eRbTHj2KLro",
  },
  {
    id: "wim-2025-men-final-3",
    video_id: "eRbTHj2KLro",
    start_at_s: 95,
    pause_at_s: 107,
    caption: "Sinner vs Alcaraz · Wimbledon 2025 final",
    options: [
      "Crosscourt",
      "Down the line",
      "Lob",
      "Body shot",
    ],
    correct_index: 0,
    source_url: "https://www.youtube.com/watch?v=eRbTHj2KLro",
  },
  {
    id: "wim-2025-women-final-1",
    video_id: "X4dVyRyY7TY",
    start_at_s: 32,
    pause_at_s: 37,
    caption: "Świątek vs Anisimova · Wimbledon 2025 final",
    options: [
      "Down the line",
      "Cross-court winner",
      "Body serve",
      "Drop shot",
    ],
    correct_index: 0,
    source_url: "https://www.youtube.com/watch?v=X4dVyRyY7TY",
  },
];
