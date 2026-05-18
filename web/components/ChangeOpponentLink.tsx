"use client";

import { useState } from "react";

import { OpponentPicker } from "@/components/OpponentPicker";

/**
 * Inline "change opponent" toggle for the H2H page. Click → reveals
 * a small autocomplete; pick a player → navigates to the new H2H URL.
 * Esc / click "Cancel" backs out.
 */
export function ChangeOpponentLink({
  anchorSlug,
  tourFilter,
}: {
  anchorSlug: string;
  /** Restrict opponent results to this tour (the anchor's). */
  tourFilter?: string | null;
}) {
  const [open, setOpen] = useState(false);
  if (open) {
    return (
      <div className="space-y-1">
        <OpponentPicker
          anchorSlug={anchorSlug}
          tourFilter={tourFilter}
          compact
          onCancel={() => setOpen(false)}
        />
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="text-[10px] text-text-muted underline decoration-dotted hover:text-text-secondary"
        >
          cancel
        </button>
      </div>
    );
  }
  return (
    <button
      type="button"
      onClick={() => setOpen(true)}
      className="text-[10px] text-text-muted underline decoration-dotted hover:text-text-secondary"
    >
      change opponent
    </button>
  );
}
