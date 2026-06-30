"use client";

import { useEffect, useState } from "react";

/**
 * Shared YouTube IFrame Player API plumbing. Both the Call the Shot
 * round (player consumer) and the Call the Shot builder (operator
 * tool) load the same API, so the type declarations + the ready
 * hook live here to keep duplicate `namespace YT { ... }` blocks out
 * of multiple files (TS forbids that).
 */

declare global {
  interface Window {
    onYouTubeIframeAPIReady?: () => void;
    YT?: typeof YT;
  }
  // Minimal slice of the YT namespace we use. Real types come from
  // @types/youtube but the surface area is small enough to avoid that
  // dependency.
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


/**
 * Returns true once `window.YT.Player` is available. Loads the IFrame
 * API script if it's not already on the page. Plays nicely with other
 * components that may have loaded the API first.
 */
export function useYouTubeApiReady(): boolean {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (window.YT && (window.YT as unknown as { Player?: unknown }).Player) {
      setReady(true);
      return;
    }
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
