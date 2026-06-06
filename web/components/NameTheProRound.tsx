"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import type { NameTheProImage, NameTheProSet } from "@/lib/api";

/**
 * Round-mode play for Name the Pro: walk through 5 multiple-choice
 * images, score cumulatively, summary at the end.
 *
 * Storage:
 *   - mob:ntp:set:{set_id}      → completed-round summary
 *   - mob:ntp:image-scores:v1   → per-image first-answer (for archive
 *                                  badges + dedupe)
 */

const SET_KEY_PREFIX = "mob:ntp:set:";
const IMAGE_SCORES_KEY = "mob:ntp:image-scores:v1";

const POINTS_PER_CORRECT = 100;

type ImageResult = {
  image_id: number;
  picked_slug: string;
  correct_slug: string;
  is_correct: boolean;
  points: number;
  // Snapshot of the image's display fields at result-save time —
  // means the summary survives admin deletions or re-bundles.
  caption?: string;
  image_url?: string;
};

type RoundSummary = {
  set_id: number;
  results: ImageResult[];
  total_points: number;
  completed_at: string;
};

type StoredImageScore = {
  image_id: number;
  is_correct: boolean;
  played_at: string;
};


function loadSetSummary(set_id: number): RoundSummary | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(SET_KEY_PREFIX + set_id);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveSetSummary(round: RoundSummary): void {
  localStorage.setItem(SET_KEY_PREFIX + round.set_id, JSON.stringify(round));
}

function saveImageScoreIfFirst(r: ImageResult): void {
  try {
    const all: Record<string, StoredImageScore> =
      JSON.parse(localStorage.getItem(IMAGE_SCORES_KEY) || "{}");
    if (all[r.image_id]) return;
    all[r.image_id] = {
      image_id: r.image_id,
      is_correct: r.is_correct,
      played_at: new Date().toISOString(),
    };
    localStorage.setItem(IMAGE_SCORES_KEY, JSON.stringify(all));
  } catch {
    /* localStorage might be disabled */
  }
}


export function NameTheProRound({
  set: thisSet,
}: {
  set: NameTheProSet;
}) {
  const [savedSummary, setSavedSummary] = useState<RoundSummary | null>(null);
  const [practice, setPractice] = useState(false);
  const [idx, setIdx] = useState(0);
  const [results, setResults] = useState<ImageResult[]>([]);
  const [picked, setPicked] = useState<string | null>(null);

  useEffect(() => {
    const prior = loadSetSummary(thisSet.id);
    if (prior) setSavedSummary(prior);
  }, [thisSet.id]);

  const total = thisSet.images.length;
  const current = thisSet.images[idx] ?? null;
  const revealed = picked !== null;

  const cumulativePoints = useMemo(
    () => results.reduce((s, r) => s + r.points, 0),
    [results],
  );

  const onPick = useCallback((slug: string) => {
    if (revealed || !current) return;
    setPicked(slug);
  }, [revealed, current]);

  const advance = useCallback(() => {
    if (!current || !picked) return;
    const is_correct = picked === current.correct_player_slug;
    const result: ImageResult = {
      image_id: current.id,
      picked_slug: picked,
      correct_slug: current.correct_player_slug,
      is_correct,
      points: is_correct ? POINTS_PER_CORRECT : 0,
      caption: current.caption,
      image_url: current.image_url,
    };
    if (!practice) saveImageScoreIfFirst(result);

    const next = [...results, result];
    setResults(next);
    setPicked(null);

    if (idx + 1 < total) {
      setIdx(idx + 1);
    } else {
      const summary: RoundSummary = {
        set_id: thisSet.id,
        results: next,
        total_points: next.reduce((s, r) => s + r.points, 0),
        completed_at: new Date().toISOString(),
      };
      if (!practice) saveSetSummary(summary);
      setSavedSummary(summary);
    }
  }, [current, picked, idx, total, results, practice, thisSet.id]);

  // Auto-advance on the LAST image (matches STB UX): once the answer
  // is revealed, give the player ~1.6s to register correct/wrong then
  // transition to the summary without needing a button tap.
  useEffect(() => {
    if (!revealed || idx + 1 < total) return;
    const t = setTimeout(() => advance(), 1600);
    return () => clearTimeout(t);
  }, [revealed, idx, total, advance]);

  if (savedSummary && !practice) {
    return (
      <RoundSummaryView
        summary={savedSummary}
        images={thisSet.images}
        onReplay={() => {
          setPractice(true);
          setSavedSummary(null);
          setIdx(0);
          setResults([]);
          setPicked(null);
        }}
      />
    );
  }

  if (!current) {
    return <p className="text-sm text-text-muted">This set is empty.</p>;
  }

  const correct_slug = current.correct_player_slug;
  const correct_name =
    current.options.find((o) => o.slug === correct_slug)?.full_name ?? current.caption;

  return (
    <div className="space-y-4">
      <RoundHeader
        title={thisSet.title}
        idx={idx}
        total={total}
        cumulative={cumulativePoints}
        practice={practice}
      />

      <div
        className="relative w-full select-none overflow-hidden rounded-lg border border-ink-700 bg-ink-900"
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={current.image_url}
          alt={revealed ? correct_name : "Name this player"}
          className="block h-auto w-full"
          draggable={false}
        />
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {current.options.map((opt) => {
          const isPicked = picked === opt.slug;
          const isCorrect = opt.slug === correct_slug;
          let tone =
            "border-ink-700 bg-ink-900 text-text-primary hover:bg-ink-800";
          if (revealed) {
            if (isCorrect) {
              tone =
                "border-emerald-500/50 bg-emerald-500/10 text-emerald-700 font-semibold";
            } else if (isPicked) {
              tone =
                "border-red-500/50 bg-red-500/10 text-red-700 font-semibold";
            } else {
              tone = "border-ink-700 bg-ink-900 text-text-muted";
            }
          }
          return (
            <button
              key={opt.slug}
              type="button"
              disabled={revealed}
              onClick={() => onPick(opt.slug)}
              className={`rounded-md border px-4 py-3 text-left text-sm transition ${tone}`}
            >
              {opt.full_name}
            </button>
          );
        })}
      </div>

      {revealed && (
        <ResultPanel
          is_correct={picked === correct_slug}
          correct_name={correct_name}
        />
      )}

      {revealed && idx + 1 < total && (
        <button
          type="button"
          onClick={advance}
          className="w-full rounded-md bg-accent px-4 py-3 text-sm font-bold uppercase tracking-wider text-white hover:bg-accent-dim"
        >
          Next ({idx + 2}/{total}) →
        </button>
      )}
      {revealed && idx + 1 >= total && (
        <div className="rounded-md border border-ink-700 bg-ink-900 px-4 py-3 text-center text-sm text-text-secondary">
          Tallying your round…
        </div>
      )}

      {(current.credit || current.source_url) && (
        <div className="text-[11px] text-text-muted">
          {current.credit && <span>Photo: {current.credit}</span>}
          {current.source_url && (
            <>
              {" · "}
              <a
                href={current.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="underline decoration-dotted underline-offset-2 hover:text-text-secondary"
              >
                source
              </a>
            </>
          )}
        </div>
      )}
    </div>
  );
}


function RoundHeader({
  title,
  idx,
  total,
  cumulative,
  practice,
}: {
  title: string | null;
  idx: number;
  total: number;
  cumulative: number;
  practice: boolean;
}) {
  return (
    <header className="flex items-baseline justify-between gap-3">
      <div>
        <div className="text-[10px] font-bold uppercase tracking-wider text-accent">
          {practice ? "Practice" : title || "Today's round"}
        </div>
        <h1 className="mt-1 text-2xl font-bold tracking-tight">
          Name the pro · {idx + 1} of {total}
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
  );
}


function ResultPanel({
  is_correct,
  correct_name,
}: {
  is_correct: boolean;
  correct_name: string;
}) {
  const headline = is_correct ? "🎾  Correct" : "❌  Wrong";
  const tone = is_correct
    ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-700"
    : "border-red-500/40 bg-red-500/10 text-red-700";
  return (
    <div className={`rounded-md border p-4 ${tone}`}>
      <div className="text-lg font-semibold">{headline}</div>
      <div className="mt-1 text-xs uppercase tracking-wider opacity-80">
        {is_correct
          ? `+${POINTS_PER_CORRECT} pts`
          : `It was ${correct_name}`}
      </div>
    </div>
  );
}


function RoundSummaryView({
  summary,
  images,
  onReplay,
}: {
  summary: RoundSummary;
  images: NameTheProImage[];
  onReplay: () => void;
}) {
  const max_possible = images.length * POINTS_PER_CORRECT;
  return (
    <div className="space-y-5">
      <header>
        <div className="text-[10px] font-bold uppercase tracking-wider text-accent">
          Round complete
        </div>
        <h1 className="mt-1 text-3xl font-bold tracking-tight">
          {summary.total_points}{" "}
          <span className="text-lg font-medium text-text-muted">/ {max_possible}</span>
        </h1>
      </header>

      <ShareCard summary={summary} setId={summary.set_id} />

      <ul className="divide-y divide-ink-700 overflow-hidden rounded-lg border border-ink-700 bg-ink-900">
        {summary.results.map((r) => {
          const live = images.find((i) => i.id === r.image_id);
          const caption = r.caption ?? live?.caption ?? `Image #${r.image_id}`;
          const image_url = r.image_url ?? live?.image_url;
          const tone = r.is_correct ? "text-emerald-700" : "text-red-700";
          const verdict = r.is_correct ? "Correct" : "Wrong";
          return (
            <li key={r.image_id} className="flex items-center gap-3 p-3">
              {image_url && (
                /* eslint-disable-next-line @next/next/no-img-element */
                <img
                  src={image_url}
                  alt=""
                  className="h-12 w-20 shrink-0 rounded object-cover"
                />
              )}
              <div className="flex-1 min-w-0">
                <div className="line-clamp-1 text-sm font-medium text-text-primary">
                  {caption}
                </div>
                <div className={`text-xs ${tone}`}>
                  {verdict}
                </div>
              </div>
              <div className="shrink-0 text-right">
                <div className="text-lg font-bold tabular-nums">{r.points}</div>
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
        Replay this round (practice — no score saved)
      </button>
    </div>
  );
}


/**
 * Wordle-style share card. Pattern: 🟩 correct, 🟥 wrong.
 * Text format:
 *   🎾 mob.tennis · Name the Pro · 400/500
 *   🟩 🟥 🟩 🟩 🟩
 *   mob.tennis/play/name-the-pro/sets/123
 */
function ShareCard({
  summary,
  setId,
}: {
  summary: RoundSummary;
  setId: number;
}) {
  const [copied, setCopied] = useState(false);

  const max_possible = summary.results.length * POINTS_PER_CORRECT;
  const pattern = summary.results
    .map((r) => (r.is_correct ? "🟩" : "🟥"))
    .join("");
  const origin =
    typeof window !== "undefined" ? window.location.origin : "https://mob.tennis";
  const shareUrl = `${origin}/play/name-the-pro/sets/${setId}`;
  const text =
    `🎾 mob.tennis · Name the Pro · ${summary.total_points}/${max_possible}\n` +
    `${pattern}\n` +
    shareUrl;

  const onShare = async () => {
    if (typeof navigator !== "undefined" && "share" in navigator) {
      try {
        await navigator.share({ title: "Name the Pro", text });
        return;
      } catch {
        /* user cancelled or unsupported — fall through to clipboard */
      }
    }
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard unavailable */
    }
  };

  return (
    <div className="rounded-md border border-ink-700 bg-ink-900 p-4 space-y-3">
      <div className="space-y-1">
        <div className="text-[10px] font-bold uppercase tracking-wider text-text-muted">
          Share your round
        </div>
        <pre className="text-base leading-relaxed text-text-primary whitespace-pre-wrap font-sans">
          {text}
        </pre>
      </div>
      <button
        type="button"
        onClick={onShare}
        className="w-full rounded-md border border-accent/40 bg-accent/10 px-4 py-2 text-sm font-bold text-accent hover:bg-accent/20"
      >
        {copied ? "Copied to clipboard ✓" : "Share"}
      </button>
    </div>
  );
}
