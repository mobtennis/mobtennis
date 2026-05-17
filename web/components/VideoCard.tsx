"use client";

import { useEffect, useState } from "react";

import type { VideoItemSummary } from "@/lib/api";
import { EVENTS } from "@/lib/analytics";
import { analytics } from "@/lib/analytics-client";
import { parseUtcIso } from "@/lib/format";

/**
 * YouTube highlight card. The frame's aspect ratio follows
 * `video.is_portrait` — 16:9 for landscape, 9:16 for portrait shorts
 * (with a "Shorts" badge) — so vertical videos don't render
 * letterboxed in a 16:9 frame. Card width is controlled by the
 * parent (e.g. a masonry column); we no longer cap portrait width
 * here. Both play inline via a click-to-swap iframe.
 *
 * One-video-at-a-time: starting a card dispatches a window-level
 * `tennismob:video-play` event with its own video_id; every other
 * card listens and stops itself if the event id differs. Keeps
 * audio sane when multiple highlights are on screen.
 *
 * Lazy embed: we don't render the iframe until the user clicks.
 * Loading every highlight player up-front would bundle hundreds of
 * KB of YouTube JS per page (one full player per video).
 *
 * Embedding via YouTube's iframe is explicitly TOS-allowed: playback
 * goes through their player, monetisation + analytics stay with the
 * channel, and we never re-host bytes.
 */

const VIDEO_PLAY_EVENT = "tennismob:video-play";

function broadcastPlay(videoId: string) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(VIDEO_PLAY_EVENT, { detail: videoId }));
}

function useStopOnOtherPlay(ownId: string, stop: () => void) {
  useEffect(() => {
    const onPlay = (e: Event) => {
      const id = (e as CustomEvent<string>).detail;
      if (id !== ownId) stop();
    };
    window.addEventListener(VIDEO_PLAY_EVENT, onPlay as EventListener);
    return () => window.removeEventListener(VIDEO_PLAY_EVENT, onPlay as EventListener);
  }, [ownId, stop]);
}

export function VideoCard({ video }: { video: VideoItemSummary }) {
  const [playing, setPlaying] = useState(false);
  useStopOnOtherPlay(video.video_id, () => setPlaying(false));

  const portrait = !!video.is_portrait;
  const channelLabel = video.channel_name ?? video.source;
  const published = parseUtcIso(video.published_at).toLocaleDateString([], {
    month: "short",
    day: "numeric",
  });

  return (
    <article className="overflow-hidden rounded-md border border-ink-700 bg-ink-900 shadow-card">
      <div
        className={`relative w-full bg-ink-950 ${portrait ? "aspect-[9/16]" : "aspect-video"}`}
      >
        {playing ? (
          <iframe
            // Privacy-enhanced domain avoids dropping tracking cookies
            // until the user explicitly plays. Autoplay works because
            // it was just user-initiated. `playsinline` keeps portrait
            // videos in-place on iOS instead of jumping to fullscreen.
            src={`https://www.youtube-nocookie.com/embed/${video.video_id}?autoplay=1&rel=0&playsinline=1`}
            title={video.title}
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
            className="absolute inset-0 h-full w-full"
          />
        ) : (
          <button
            type="button"
            onClick={() => {
              broadcastPlay(video.video_id);
              setPlaying(true);
              analytics.track(EVENTS.newsClicked, {
                kind: "video",
                video_id: video.video_id,
                source: video.source,
                orientation: portrait ? "portrait" : "landscape",
              });
            }}
            className="group absolute inset-0 h-full w-full"
            aria-label={`Play: ${video.title}`}
          >
            {video.thumbnail_url && (
              // <img> not next/image — YouTube CDN URLs get no benefit
              // from Next.js image optimisation and would only add
              // Vercel transform cost.
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={video.thumbnail_url}
                alt={video.title}
                className="absolute inset-0 h-full w-full object-cover transition group-hover:brightness-90"
                loading="lazy"
              />
            )}
            <span className="absolute inset-0 flex items-center justify-center">
              <span className="flex h-14 w-14 items-center justify-center rounded-full bg-black/60 text-white transition group-hover:scale-110 group-hover:bg-accent">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                  <path d="M8 5v14l11-7z" />
                </svg>
              </span>
            </span>
            {portrait && (
              <span className="absolute left-2 top-2 rounded-full bg-black/70 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-white">
                Shorts
              </span>
            )}
          </button>
        )}
      </div>
      <div className="px-3 py-2">
        <h3 className="text-sm font-semibold text-text-primary line-clamp-2">{video.title}</h3>
        <p className="mt-1 text-[11px] text-text-muted">
          {channelLabel} · {published}
        </p>
      </div>
    </article>
  );
}
