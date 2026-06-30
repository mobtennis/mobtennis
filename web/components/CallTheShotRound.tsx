"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { CallTheShotItem } from "@/lib/call-the-shot-data";

/**
 * Prototype Call the Shot round. Loads the YouTube IFrame Player API
 * inline, plays each item up to its `pause_at_s`, freezes the video,
 * surfaces 4 prediction buttons. On pick, reveals the answer and
 * resumes the clip for `resume_for_s` seconds before advancing.
 *
 * Scope (prototype):
 *   - No localStorage round summary yet — we're feeling out whether
 *     the pause/resume rhythm even works. Add later if UX lands.
 *   - No share card.
 *   - Static items, no daily set / archive concept.
 *
 * Notes:
 *   - playsinline=1 is essential or iOS hijacks to native fullscreen,
 *     which breaks our overlay + button row.
 *   - YouTube blocks unmuted autoplay on every mobile browser; the
 *     first item requires a tap to start. Subsequent items reuse the
 *     same Player instance so they can auto-cue without re-priming.
 *   - We poll currentTime every 250ms to catch the pause moment —
 *     onStateChange fires too late (only on natural state transitions)
 *     to land within a few frames of the intended timestamp.
 */

const POINTS_PER_CORRECT = 100;

type Verdict = "pending" | "correct" | "wrong";

type Result = {
  item_id: string;
  picked_index: number;
  correct_index: number;
  is_correct: boolean;
};

declare global {
  interface Window {
    onYouTubeIframeAPIReady?: () => void;
    YT?: typeof YT;
  }
  // Minimal slice of the YT namespace we use. The real types come from
  // @types/youtube but we avoid that dep — surface area is small.
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace YT {
    class Player {
      constructor(el: string | HTMLElement, opts: PlayerOptions);
      playVideo(): void;
      pauseVideo(): void;
      seekTo(s: number, allowSeekAhead: boolean): void;
      loadVideoById(args: { videoId: string; startSeconds?: number }): void;
      getCurrentTime(): number;
      getPlayerState(): number;
      destroy(): void;
    }
    interface PlayerOptions {
      videoId?: string;
      width?: number | string;
      height?: number | string;
      playerVars?: Record<string, string | number>;
      events?: {
        onReady?: (e: { target: Player }) => void;
        onStateChange?: (e: { data: number; target: Player }) => void;
      };
    }
    enum PlayerState {
      UNSTARTED = -1, ENDED = 0, PLAYING = 1, PAUSED = 2, BUFFERING = 3, CUED = 5,
    }
  }
}


function useYouTubeApiReady(): boolean {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (window.YT && (window.YT as unknown as { Player?: unknown }).Player) {
      setReady(true);
      return;
    }
    // Chain onto any existing handler so we play nicely if another
    // component loaded the API first.
    const prior = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => {
      prior?.();
      setReady(true);
    };
    const existing = document.querySelector<HTMLScriptElement>(
      'script[src="https://www.youtube.com/iframe_api"]',
    );
    if (!existing) {
      const s = document.createElement("script");
      s.src = "https://www.youtube.com/iframe_api";
      document.head.appendChild(s);
    }
  }, []);
  return ready;
}


export function CallTheShotRound({
  items,
}: {
  items: CallTheShotItem[];
}) {
  const apiReady = useYouTubeApiReady();
  const containerId = "cts-player";
  const playerRef = useRef<YT.Player | null>(null);
  const pollRef = useRef<number | null>(null);

  const [idx, setIdx] = useState(0);
  const [results, setResults] = useState<Result[]>([]);
  const [verdict, setVerdict] = useState<Verdict>("pending");
  const [pickedIdx, setPickedIdx] = useState<number | null>(null);
  const [paused, setPaused] = useState(false);
  const [started, setStarted] = useState(false);

  const current = items[idx] ?? null;

  const stopPoll = useCallback(() => {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  // Poll currentTime and pause when we cross the target. 50ms = ~3
  // frames at 60fps, tight enough to feel frame-accurate without
  // burning CPU. After pausing, we ALSO seek back to the exact
  // target so the displayed frame is independent of when we caught
  // the crossing (the player might have pushed past by a few frames).
  const startPollForPause = useCallback((targetS: number) => {
    stopPoll();
    pollRef.current = window.setInterval(() => {
      const p = playerRef.current;
      if (!p) return;
      try {
        if (p.getCurrentTime() >= targetS) {
          p.pauseVideo();
          // Frame-lock to the exact pause point.
          p.seekTo(targetS, true);
          setPaused(true);
          stopPoll();
        }
      } catch {
        /* player gone or not ready yet — try again next tick */
      }
    }, 50);
  }, [stopPoll]);

  // Build the player ONCE the IFrame API is loaded. We keep the
  // same Player instance across items and just call loadVideoById
  // on advance.
  //
  // Polling is started explicitly when we want to catch a pause (on
  // Tap-to-start, and after each loadVideoById in advance). The
  // `onStateChange` callback used to start polling itself on
  // PLAYING but that broke after the user resumed post-pick:
  // playVideo → PLAYING event → poll restarts → immediately
  // catches the already-crossed pause_at_s → pauses again. We
  // were resuming and re-pausing within 50ms.
  useEffect(() => {
    if (!apiReady || playerRef.current || !items[0]) return;
    const initial = items[0];
    playerRef.current = new window.YT!.Player(containerId, {
      videoId: initial.video_id,
      playerVars: {
        playsinline: 1,         // iOS: keep video inline, no native fullscreen
        modestbranding: 1,      // strips most YT branding chrome
        rel: 0,                 // no end-of-video "related" overlay
        controls: 1,            // keep native controls — backstop if our pause logic glitches
        enablejsapi: 1,
        start: initial.start_at_s ? Math.floor(initial.start_at_s) : 0,
      },
      events: {
        onReady: ({ target }) => {
          // Seek to start_at_s up front so the user doesn't watch the
          // intro card. The `start` playerVar above also does this but
          // YT is inconsistent about honouring it across cue/load paths.
          if (initial.start_at_s) {
            try { target.seekTo(initial.start_at_s, true); } catch { /* ignore */ }
          }
        },
      },
    });
    return () => {
      stopPoll();
      // Don't destroy on every render — only on unmount of this hook's
      // owning component. React 18 strict mode invokes effects twice;
      // the cleanup here only runs on actual unmount.
    };
    // Intentionally [apiReady, items[0]?.id] — we only want to build
    // the player when the API loads, and never rebuild for later
    // items. `current` and `paused` were here before and caused the
    // stale-closure bug in onStateChange.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiReady, items[0]?.id]);

  // On unmount, drop the player.
  useEffect(() => () => {
    stopPoll();
    try { playerRef.current?.destroy(); } catch { /* ignore */ }
    playerRef.current = null;
  }, [stopPoll]);

  const onPick = useCallback((option_index: number) => {
    if (!current || verdict !== "pending") return;
    const is_correct = option_index === current.correct_index;
    setPickedIdx(option_index);
    setVerdict(is_correct ? "correct" : "wrong");
    setResults((prev) => [
      ...prev,
      {
        item_id: current.id,
        picked_index: option_index,
        correct_index: current.correct_index,
        is_correct,
      },
    ]);
    // Resume the clip so the player sees how the point ended. They
    // advance manually via the Next button — point lengths vary too
    // much for a single auto-advance timer to feel right (it either
    // chops off the celebration or stalls on a black frame after the
    // clip's own outro).
    const p = playerRef.current;
    if (p) {
      try { p.playVideo(); } catch { /* ignore */ }
    }
  }, [current, verdict]);

  const advance = useCallback(() => {
    if (idx + 1 >= items.length) {
      // Round complete. Leave the verdict state alone so the summary
      // can render off results.
      setIdx(items.length);
      return;
    }
    const nextItem = items[idx + 1];
    const sameVideo = current?.video_id === nextItem.video_id;
    setIdx(idx + 1);
    setVerdict("pending");
    setPickedIdx(null);
    setPaused(false);
    const p = playerRef.current;
    if (p && nextItem) {
      try {
        if (sameVideo) {
          // Same video, just jump to the new start point. Saves the
          // reload + buffer wait and keeps the iOS gesture grant
          // (loadVideoById occasionally drops the autoplay
          // permission, forcing a manual tap to resume).
          p.seekTo(nextItem.start_at_s ?? 0, true);
          p.playVideo();
        } else {
          p.loadVideoById({
            videoId: nextItem.video_id,
            startSeconds: nextItem.start_at_s ?? 0,
          });
        }
      } catch { /* ignore */ }
      // Start polling for the NEW pause point now. getCurrentTime
      // returns 0 until the new video starts streaming (load path)
      // or jumps to start_at_s immediately (seek path), so the poll
      // is no-op until the video actually plays past pause_at_s.
      startPollForPause(nextItem.pause_at_s);
    }
  }, [idx, items, current, startPollForPause]);

  const cumulative = useMemo(
    () => results.filter((r) => r.is_correct).length * POINTS_PER_CORRECT,
    [results],
  );

  if (idx >= items.length) {
    return <Summary results={results} items={items} onReplay={() => {
      setIdx(0); setResults([]); setVerdict("pending"); setPickedIdx(null); setPaused(false);
      const p = playerRef.current;
      if (p && items[0]) {
        try {
          p.loadVideoById({
            videoId: items[0].video_id,
            startSeconds: items[0].start_at_s ?? 0,
          });
        } catch { /* ignore */ }
        startPollForPause(items[0].pause_at_s);
      }
    }} />;
  }

  if (!current) {
    return <p className="text-sm text-text-muted">No clips loaded.</p>;
  }

  return (
    <div className="space-y-4">
      <header className="flex items-baseline justify-between gap-3">
        <div>
          <div className="text-[10px] font-bold uppercase tracking-wider text-accent">
            Prototype
          </div>
          <h1 className="mt-1 text-2xl font-bold tracking-tight">
            Call the shot · {idx + 1} of {items.length}
          </h1>
        </div>
        <div className="text-right">
          <div className="text-[10px] uppercase tracking-wider text-text-muted">
            So far
          </div>
          <div className="text-2xl font-bold tabular-nums text-text-primary">
            {cumulative}
          </div>
        </div>
      </header>

      <div className="text-xs uppercase tracking-wider text-text-muted">
        {current.caption}
      </div>

      <div className="relative aspect-video w-full overflow-hidden rounded-lg border border-ink-700 bg-black">
        <div id={containerId} className="absolute inset-0 h-full w-full" />
        {!started && (
          <button
            type="button"
            onClick={() => {
              setStarted(true);
              try { playerRef.current?.playVideo(); } catch { /* ignore */ }
              if (current) startPollForPause(current.pause_at_s);
            }}
            className="absolute inset-0 flex items-center justify-center bg-black/60 text-sm font-bold uppercase tracking-wider text-white hover:bg-black/40"
          >
            Tap to start
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {current.options.map((opt, i) => {
          const isPicked = pickedIdx === i;
          const isCorrect = i === current.correct_index;
          let tone = "border-ink-700 bg-ink-900 text-text-primary hover:bg-ink-800";
          if (verdict !== "pending") {
            if (isCorrect) {
              tone = "border-emerald-500/50 bg-emerald-500/10 text-emerald-700 font-semibold";
            } else if (isPicked) {
              tone = "border-red-500/50 bg-red-500/10 text-red-700 font-semibold";
            } else {
              tone = "border-ink-700 bg-ink-900 text-text-muted";
            }
          }
          return (
            <button
              key={i}
              type="button"
              disabled={verdict !== "pending" || !paused}
              onClick={() => onPick(i)}
              className={`rounded-md border px-4 py-3 text-left text-sm transition disabled:cursor-not-allowed disabled:opacity-60 ${tone}`}
            >
              {opt}
            </button>
          );
        })}
      </div>

      {!paused && started && verdict === "pending" && (
        <div className="rounded-md border border-ink-700 bg-ink-900 px-4 py-3 text-center text-sm text-text-secondary">
          Watching the point…
        </div>
      )}
      {paused && verdict === "pending" && (
        <div className="rounded-md border border-accent/40 bg-accent/10 px-4 py-3 text-center text-sm font-semibold text-accent">
          Where's this shot going?
        </div>
      )}
      {verdict !== "pending" && (
        <>
          <div
            className={`rounded-md border p-4 ${
              verdict === "correct"
                ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-700"
                : "border-red-500/40 bg-red-500/10 text-red-700"
            }`}
          >
            <div className="text-lg font-semibold">
              {verdict === "correct" ? "🎾  Called it" : "❌  Missed"}
            </div>
            <div className="mt-1 text-xs uppercase tracking-wider opacity-80">
              Watch the point finish, then advance.
            </div>
          </div>
          <button
            type="button"
            onClick={advance}
            className="w-full rounded-md bg-accent px-4 py-3 text-sm font-bold uppercase tracking-wider text-white hover:bg-accent-dim"
          >
            {idx + 1 < items.length
              ? `Next (${idx + 2}/${items.length}) →`
              : "See results →"}
          </button>
        </>
      )}

      {current.source_url && (
        <div className="text-[11px] text-text-muted">
          <a
            href={current.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="underline decoration-dotted underline-offset-2 hover:text-text-secondary"
          >
            source
          </a>
        </div>
      )}
    </div>
  );
}


function Summary({
  results,
  items,
  onReplay,
}: {
  results: Result[];
  items: CallTheShotItem[];
  onReplay: () => void;
}) {
  const correct = results.filter((r) => r.is_correct).length;
  const max = items.length * POINTS_PER_CORRECT;
  return (
    <div className="space-y-5">
      <header>
        <div className="text-[10px] font-bold uppercase tracking-wider text-accent">
          Round complete
        </div>
        <h1 className="mt-1 text-3xl font-bold tracking-tight">
          {correct * POINTS_PER_CORRECT}{" "}
          <span className="text-lg font-medium text-text-muted">/ {max}</span>
        </h1>
        <p className="mt-1 text-sm text-text-secondary">
          {correct} of {items.length} called correctly.
        </p>
      </header>

      <ul className="divide-y divide-ink-700 overflow-hidden rounded-lg border border-ink-700 bg-ink-900">
        {results.map((r) => {
          const item = items.find((i) => i.id === r.item_id);
          const tone = r.is_correct ? "text-emerald-700" : "text-red-700";
          return (
            <li key={r.item_id} className="flex items-center gap-3 p-3">
              <div className="flex-1 min-w-0">
                <div className="line-clamp-1 text-sm font-medium text-text-primary">
                  {item?.caption ?? r.item_id}
                </div>
                <div className={`text-xs ${tone}`}>
                  Picked: {item?.options[r.picked_index] ?? "?"}{" "}
                  {!r.is_correct && (
                    <>· correct: {item?.options[r.correct_index] ?? "?"}</>
                  )}
                </div>
              </div>
              <div className="shrink-0 text-right">
                <div className="text-lg font-bold tabular-nums">
                  {r.is_correct ? POINTS_PER_CORRECT : 0}
                </div>
                <div className="text-[10px] uppercase tracking-wider text-text-muted">
                  pts
                </div>
              </div>
            </li>
          );
        })}
      </ul>

      <button
        type="button"
        onClick={onReplay}
        className="w-full rounded-md border border-ink-700 px-4 py-3 text-sm font-medium text-text-secondary hover:bg-ink-800"
      >
        Replay
      </button>
    </div>
  );
}
