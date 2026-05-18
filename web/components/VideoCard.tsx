"use client";

import { useState } from "react";

import type { VideoItemSummary } from "@/lib/api";
import { EVENTS } from "@/lib/analytics";
import { analytics } from "@/lib/analytics-client";
import { VideoModal } from "@/components/VideoModal";
import { parseUtcIso } from "@/lib/format";

/**
 * YouTube highlight card. The card itself stays compact (column
 * width, matching the news cards next to it). Click the thumbnail
 * to open a modal where the video plays at native size against a
 * blurred backdrop — bigger when you want to watch, small when
 * you're just scanning the feed.
 *
 * Card aspect follows `video.is_portrait` (9:16 vs 16:9) so the
 * thumbnail isn't letterboxed. Modal handles its own aspect ratio.
 *
 * Embedding via YouTube's iframe is explicitly TOS-allowed: playback
 * goes through their player, monetisation + analytics stay with the
 * channel, and we never re-host bytes.
 */
export function VideoCard({ video }: { video: VideoItemSummary }) {
  const [open, setOpen] = useState(false);
  const portrait = !!video.is_portrait;
  const channelLabel = video.channel_name ?? video.source;
  const published = parseUtcIso(video.published_at).toLocaleDateString([], {
    month: "short",
    day: "numeric",
  });

  return (
    <>
      <article className="overflow-hidden rounded-md border border-ink-700 bg-ink-900 shadow-card">
        <button
          type="button"
          onClick={() => {
            setOpen(true);
            analytics.track(EVENTS.newsClicked, {
              kind: "video",
              video_id: video.video_id,
              source: video.source,
              orientation: portrait ? "portrait" : "landscape",
            });
          }}
          className={`group relative block w-full bg-ink-950 ${portrait ? "aspect-[9/16]" : "aspect-video"}`}
          aria-label={`Play: ${video.title}`}
        >
          {video.thumbnail_url && (
            // <img> not next/image — YouTube CDN URLs get no benefit
            // from Next.js image optimisation and would only add Vercel
            // transform cost.
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={video.thumbnail_url}
              alt={video.title}
              className="absolute inset-0 h-full w-full object-cover transition group-hover:brightness-90"
              loading="lazy"
            />
          )}
          <span className="absolute inset-0 flex items-center justify-center">
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-black/60 text-white transition group-hover:scale-110 group-hover:bg-accent">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
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
        <div className="px-3 py-2">
          <h3 className="text-sm font-semibold text-text-primary line-clamp-2">{video.title}</h3>
          <p className="mt-1 text-[11px] text-text-muted">
            {channelLabel} · {published}
          </p>
        </div>
      </article>
      {open && <VideoModal video={video} onClose={() => setOpen(false)} />}
    </>
  );
}
