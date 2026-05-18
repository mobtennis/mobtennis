"use client";

import { useEffect } from "react";

import type { VideoItemSummary } from "@/lib/api";

/**
 * Fullscreen playback for a video card. Blurred backdrop, video
 * centered at its native aspect ratio (16:9 landscape or 9:16
 * portrait), tap-outside / Esc to close. The card stays compact in
 * the feed; users get a full-size player when they actually want to
 * watch.
 *
 * The iframe lives inside the modal — opening creates it, closing
 * destroys it — so audio + playback stop cleanly. Autoplay works
 * because the modal opens in response to a user click.
 */
export function VideoModal({
  video,
  onClose,
}: {
  video: VideoItemSummary;
  onClose: () => void;
}) {
  // Esc to close + lock body scroll while open.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  const portrait = !!video.is_portrait;

  return (
    <div
      onClick={onClose}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-md"
      role="dialog"
      aria-modal="true"
      aria-label={video.title}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        // Portrait: cap by viewport height (keeps the whole 9:16 frame
        // visible without scrolling). Landscape: cap by viewport
        // width, with a sensible max so it doesn't get absurd on
        // wide monitors.
        className={
          portrait
            ? "relative aspect-[9/16] max-h-[90vh]"
            : "relative aspect-video w-full max-w-3xl"
        }
        style={portrait ? { maxWidth: "calc(90vh * 9 / 16)" } : undefined}
      >
        <iframe
          src={`https://www.youtube-nocookie.com/embed/${video.video_id}?autoplay=1&rel=0&playsinline=1`}
          title={video.title}
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowFullScreen
          className="absolute inset-0 h-full w-full rounded-lg shadow-2xl"
        />
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="absolute -top-10 right-0 flex h-8 w-8 items-center justify-center rounded-full bg-white/10 text-white transition hover:bg-white/20"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M6 6l12 12M6 18L18 6" />
          </svg>
        </button>
      </div>
    </div>
  );
}
