"use client";

import { useCallback, useEffect, useState } from "react";

import type { PlayerImage } from "@/lib/api";
import { SectionHeader } from "@/components/SectionHeader";

/**
 * "More photos" strip on the player profile page. Clicking a
 * thumbnail opens a lightbox carousel of every non-hidden image
 * (primary included) so users can browse the full set without
 * scrolling back, and the photographer credit + Wikipedia source
 * link live IN the lightbox — no surprise navigations away from
 * mob.tennis.
 *
 * UX notes:
 *   - Esc closes; ← / → step between images.
 *   - Click outside the photo (anywhere on the dimmed backdrop)
 *     closes too.
 *   - Body scroll is locked while open so the page doesn't drift
 *     under a tap-and-hold.
 */
export function PlayerPhotoStrip({
  images,
  fullName,
}: {
  images: PlayerImage[];
  fullName: string;
}) {
  // The strip shows only alternates (primary already lives in the
  // hero band); the lightbox lets the user step through the whole
  // collection once expanded.
  const visible = images.filter((i) => !i.is_hidden);
  const altsForStrip = visible.filter((i) => !i.is_primary);
  if (altsForStrip.length < 3) return null;

  // Cap the strip to 6 thumbs — anything longer dominates the page.
  const shown = altsForStrip.slice(0, 6);
  return (
    <section>
      <SectionHeader title="More photos" subtitle="From Wikimedia Commons" />
      <div className="mt-2 grid grid-cols-3 gap-2 md:grid-cols-6">
        {shown.map((img) => (
          <PhotoThumb
            key={img.id}
            image={img}
            fullName={fullName}
            allImages={visible}
          />
        ))}
      </div>
    </section>
  );
}


function PhotoThumb({
  image,
  fullName,
  allImages,
}: {
  image: PlayerImage;
  fullName: string;
  allImages: PlayerImage[];
}) {
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  const initialIndex = allImages.findIndex((i) => i.id === image.id);
  return (
    <>
      <button
        type="button"
        onClick={() => setOpenIndex(initialIndex >= 0 ? initialIndex : 0)}
        className="group relative aspect-[3/4] overflow-hidden rounded-md border border-ink-700 bg-ink-900 focus:outline-none focus:ring-2 focus:ring-accent"
        title={image.credit ?? undefined}
        aria-label={`View photo of ${fullName}`}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={image.url}
          alt={fullName}
          className="h-full w-full object-cover transition-opacity group-hover:opacity-90"
          loading="lazy"
        />
      </button>
      {openIndex !== null && (
        <PhotoLightbox
          images={allImages}
          startIndex={openIndex}
          fullName={fullName}
          onClose={() => setOpenIndex(null)}
        />
      )}
    </>
  );
}


function PhotoLightbox({
  images,
  startIndex,
  fullName,
  onClose,
}: {
  images: PlayerImage[];
  startIndex: number;
  fullName: string;
  onClose: () => void;
}) {
  const [idx, setIdx] = useState(startIndex);
  const current = images[idx];

  const prev = useCallback(() => {
    setIdx((i) => (i - 1 + images.length) % images.length);
  }, [images.length]);
  const next = useCallback(() => {
    setIdx((i) => (i + 1) % images.length);
  }, [images.length]);

  // Keyboard nav + body-scroll lock. Cleans up on unmount so the
  // listener doesn't outlive the modal.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      else if (e.key === "ArrowLeft") prev();
      else if (e.key === "ArrowRight") next();
    };
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [onClose, prev, next]);

  if (!current) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Photo of ${fullName}`}
      onClick={onClose}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 p-4"
    >
      {/* Click on the photo itself shouldn't close — stop the bubble. */}
      <div
        className="relative flex max-h-full max-w-5xl flex-col items-center"
        onClick={(e) => e.stopPropagation()}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={current.url}
          alt={fullName}
          className="max-h-[80vh] max-w-full rounded-md object-contain"
        />

        {(current.credit || current.source_url) && (
          <div className="mt-3 max-w-full text-center text-xs text-text-muted">
            {current.credit && (
              <span>Photo: {current.credit}</span>
            )}
            {current.license_url && (
              <>
                {" · "}
                <a
                  href={current.license_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline decoration-dotted underline-offset-2 hover:text-text-secondary"
                  onClick={(e) => e.stopPropagation()}
                >
                  license
                </a>
              </>
            )}
            {current.source_url && (
              <>
                {" · "}
                <a
                  href={current.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline decoration-dotted underline-offset-2 hover:text-text-secondary"
                  onClick={(e) => e.stopPropagation()}
                >
                  on Wikipedia
                </a>
              </>
            )}
          </div>
        )}

        <div className="mt-2 text-[11px] uppercase tracking-wider text-text-muted">
          {idx + 1} / {images.length}
        </div>

        {/* Close — top right of the modal frame, not the page edge,
            so it sits in the user's eye-line near the photo. */}
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="absolute -top-2 right-0 -translate-y-full rounded-full bg-white/10 px-3 py-1 text-sm text-white hover:bg-white/20 md:right-2 md:top-2 md:translate-y-0"
        >
          ✕
        </button>

        {images.length > 1 && (
          <>
            <button
              type="button"
              onClick={prev}
              aria-label="Previous photo"
              className="absolute left-2 top-1/2 -translate-y-1/2 rounded-full bg-white/10 px-3 py-2 text-lg text-white hover:bg-white/20 md:-left-12"
            >
              ‹
            </button>
            <button
              type="button"
              onClick={next}
              aria-label="Next photo"
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full bg-white/10 px-3 py-2 text-lg text-white hover:bg-white/20 md:-right-12"
            >
              ›
            </button>
          </>
        )}
      </div>
    </div>
  );
}
