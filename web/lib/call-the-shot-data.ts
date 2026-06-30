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
  /** Where to pause, in seconds. Fractional ok. */
  pause_at_s: number;
  /** Seconds AFTER pause to keep playing on reveal before "Next". */
  resume_for_s: number;
  /** One-line context shown under the video. */
  caption: string;
  /** 4 prediction buttons. Index 0..3 — correct_index points at the right one. */
  options: [string, string, string, string];
  correct_index: 0 | 1 | 2 | 3;
  /** Optional attribution / link out, shown small under the video. */
  source_url?: string;
};

export const CALL_THE_SHOT_ITEMS: CallTheShotItem[] = [
  // TODO(atli): replace these placeholders with real highlight clips.
  // The video_id below is a generic Rick Astley as a smoke-test fill —
  // the embed will load but the pause point is meaningless. Use it to
  // verify the UI flow, then swap in real tennis clips.
  {
    id: "demo-1",
    video_id: "dQw4w9WgXcQ",
    pause_at_s: 25,
    resume_for_s: 6,
    caption: "Sinner vs Alcaraz · placeholder",
    options: [
      "Cross-court winner",
      "Down the line",
      "Drop shot",
      "Lob",
    ],
    correct_index: 1,
  },
  {
    id: "demo-2",
    video_id: "dQw4w9WgXcQ",
    pause_at_s: 60,
    resume_for_s: 6,
    caption: "Świątek vs Sabalenka · placeholder",
    options: [
      "Down the line",
      "Cross-court winner",
      "Net cord",
      "Body serve",
    ],
    correct_index: 1,
  },
];
