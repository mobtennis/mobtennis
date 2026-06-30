"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useYouTubeApiReady } from "@/lib/youtube";

/**
 * Phase-1 admin builder for Call the Shot. No backend yet — the
 * output is a TS object literal you paste into
 * `web/lib/call-the-shot-data.ts`. Once we're happy with the UX +
 * have ~20 items, we'll move to a DB-backed model with the same
 * shape and reuse most of this component.
 *
 * Key affordances:
 *   - Paste a YouTube URL/ID, hit Load → player embeds
 *   - Custom jog buttons (1s / 0.1s / single-frame) + native YT controls
 *   - "Mark as Start" / "Mark as Pause" snapshots getCurrentTime()
 *     (sub-second precision; YT API exposes a float)
 *   - Preview button plays from start → pause and stops
 *   - Generated TS literal at the bottom, Copy button
 *   - localStorage draft so a refresh doesn't lose progress
 */

const DRAFT_KEY = "mob:cts:builder:draft:v1";

const DEFAULT_OPTIONS: [string, string, string, string] = [
  "Crosscourt",
  "Down the line",
  "Lob",
  "Body shot",
];

type Draft = {
  url_input: string;
  video_id: string;
  start_at_s: number | null;
  pause_at_s: number | null;
  caption: string;
  options: [string, string, string, string];
  correct_index: 0 | 1 | 2 | 3;
};

const EMPTY_DRAFT: Draft = {
  url_input: "",
  video_id: "",
  start_at_s: null,
  pause_at_s: null,
  caption: "",
  options: [...DEFAULT_OPTIONS] as [string, string, string, string],
  correct_index: 0,
};


/** Extract a YouTube video ID from a URL or accept a raw 11-char ID. */
function parseVideoId(input: string): string | null {
  const trimmed = input.trim();
  if (!trimmed) return null;
  // Already an 11-char ID.
  if (/^[\w-]{11}$/.test(trimmed)) return trimmed;
  try {
    const u = new URL(trimmed);
    if (u.hostname === "youtu.be") {
      const m = u.pathname.match(/^\/([\w-]{11})/);
      return m ? m[1] : null;
    }
    if (u.hostname.endsWith("youtube.com") || u.hostname.endsWith("youtube-nocookie.com")) {
      const v = u.searchParams.get("v");
      if (v && /^[\w-]{11}$/.test(v)) return v;
      // Embed / shorts URLs.
      const m = u.pathname.match(/\/(embed|shorts)\/([\w-]{11})/);
      if (m) return m[2];
    }
  } catch {
    /* not a URL */
  }
  return null;
}


function formatTime(s: number | null): string {
  if (s === null) return "—";
  const sign = s < 0 ? "-" : "";
  const abs = Math.abs(s);
  const m = Math.floor(abs / 60);
  const sec = abs - m * 60;
  return `${sign}${m}:${sec.toFixed(3).padStart(6, "0")}`;
}


function loadDraft(): Draft {
  if (typeof window === "undefined") return EMPTY_DRAFT;
  try {
    const raw = localStorage.getItem(DRAFT_KEY);
    if (!raw) return EMPTY_DRAFT;
    const parsed = JSON.parse(raw);
    return { ...EMPTY_DRAFT, ...parsed };
  } catch {
    return EMPTY_DRAFT;
  }
}


function generateItemJson(d: Draft): string {
  if (!d.video_id || d.start_at_s === null || d.pause_at_s === null) {
    return "// fill in video, start, and pause before exporting.";
  }
  const id = `item-${new Date().toISOString().slice(0, 10).replace(/-/g, "")}-${Math.floor(Math.random() * 1000)}`;
  const round = (n: number) => Math.round(n * 1000) / 1000;
  const opts = d.options.map((o) => `    ${JSON.stringify(o)},`).join("\n");
  return (
    "{\n" +
    `  id: ${JSON.stringify(id)},\n` +
    `  video_id: ${JSON.stringify(d.video_id)},\n` +
    `  start_at_s: ${round(d.start_at_s)},\n` +
    `  pause_at_s: ${round(d.pause_at_s)},\n` +
    `  caption: ${JSON.stringify(d.caption || "TODO caption")},\n` +
    `  options: [\n${opts}\n  ],\n` +
    `  correct_index: ${d.correct_index},\n` +
    `  source_url: "https://www.youtube.com/watch?v=${d.video_id}",\n` +
    "},"
  );
}


const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "https://api.mob.tennis";


export function CallTheShotBuilder({ adminKey }: { adminKey: string }) {
  const apiReady = useYouTubeApiReady();
  const playerRef = useRef<YT.Player | null>(null);
  const pollRef = useRef<number | null>(null);
  const containerId = "cts-builder-player";

  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [hydrated, setHydrated] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [fps, setFps] = useState<30 | 60>(30);
  const [copyOk, setCopyOk] = useState(false);
  const [previewPauseAt, setPreviewPauseAt] = useState<number | null>(null);

  useEffect(() => {
    setDraft(loadDraft());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (hydrated) localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
  }, [draft, hydrated]);

  // Build the player when the API + a video are both available.
  useEffect(() => {
    if (!apiReady || !draft.video_id || playerRef.current) return;
    playerRef.current = new window.YT!.Player(containerId, {
      videoId: draft.video_id,
      playerVars: {
        playsinline: 1,
        modestbranding: 1,
        rel: 0,
        controls: 1,
        enablejsapi: 1,
      },
    });
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, [apiReady, draft.video_id]);

  // When the video_id changes (user loads a different clip), swap it
  // on the existing player. Avoids tearing down + rebuilding the iframe.
  useEffect(() => {
    const p = playerRef.current;
    if (!p || !draft.video_id) return;
    try {
      p.loadVideoById({ videoId: draft.video_id, startSeconds: 0 });
    } catch { /* ignore */ }
  }, [draft.video_id]);

  // Poll currentTime so the readout updates while playing.
  useEffect(() => {
    if (!apiReady || !draft.video_id) return;
    const id = window.setInterval(() => {
      const p = playerRef.current;
      if (!p) return;
      try {
        const t = p.getCurrentTime();
        setCurrentTime(t);
        if (previewPauseAt !== null && t >= previewPauseAt) {
          p.pauseVideo();
          p.seekTo(previewPauseAt, true);
          setPreviewPauseAt(null);
        }
      } catch { /* ignore */ }
    }, 100);
    return () => window.clearInterval(id);
  }, [apiReady, draft.video_id, previewPauseAt]);

  const onLoad = useCallback(() => {
    const id = parseVideoId(draft.url_input);
    if (!id) {
      alert("Couldn't parse a video ID from that input.");
      return;
    }
    setDraft((d) => ({ ...d, video_id: id, start_at_s: null, pause_at_s: null }));
  }, [draft.url_input]);

  const seekDelta = useCallback((delta: number) => {
    const p = playerRef.current;
    if (!p) return;
    try {
      const next = Math.max(0, p.getCurrentTime() + delta);
      p.seekTo(next, true);
    } catch { /* ignore */ }
  }, []);

  const playPause = useCallback(() => {
    const p = playerRef.current;
    if (!p) return;
    try {
      // PLAYING == 1; PAUSED == 2; BUFFERING == 3
      const state = p.getPlayerState();
      if (state === 1) p.pauseVideo();
      else p.playVideo();
    } catch { /* ignore */ }
  }, []);

  const markStart = useCallback(() => {
    const p = playerRef.current;
    if (!p) return;
    try { setDraft((d) => ({ ...d, start_at_s: p.getCurrentTime() })); } catch { /* ignore */ }
  }, []);

  const markPause = useCallback(() => {
    const p = playerRef.current;
    if (!p) return;
    try { setDraft((d) => ({ ...d, pause_at_s: p.getCurrentTime() })); } catch { /* ignore */ }
  }, []);

  const preview = useCallback(() => {
    const p = playerRef.current;
    if (!p || draft.start_at_s === null || draft.pause_at_s === null) return;
    try {
      p.seekTo(draft.start_at_s, true);
      p.playVideo();
      setPreviewPauseAt(draft.pause_at_s);
    } catch { /* ignore */ }
  }, [draft.start_at_s, draft.pause_at_s]);

  const itemJson = useMemo(() => generateItemJson(draft), [draft]);

  const copyJson = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(itemJson);
      setCopyOk(true);
      setTimeout(() => setCopyOk(false), 1500);
    } catch {
      /* clipboard unavailable */
    }
  }, [itemJson]);

  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [saveError, setSaveError] = useState<string | null>(null);

  const saveItem = useCallback(async () => {
    if (!draft.video_id || draft.start_at_s === null || draft.pause_at_s === null) {
      setSaveError("video, start, and pause are all required");
      setSaveState("error");
      return;
    }
    setSaveState("saving");
    setSaveError(null);
    try {
      const res = await fetch(
        `${API_BASE}/api/admin/call-the-shot/items?key=${encodeURIComponent(adminKey)}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            video_id: draft.video_id,
            start_at_s: draft.start_at_s,
            pause_at_s: draft.pause_at_s,
            caption: draft.caption,
            options: draft.options,
            correct_index: draft.correct_index,
            source_url: `https://www.youtube.com/watch?v=${draft.video_id}`,
          }),
        },
      );
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      }
      setSaveState("saved");
      setTimeout(() => setSaveState("idle"), 2000);
    } catch (e) {
      setSaveError(String(e));
      setSaveState("error");
    }
  }, [adminKey, draft]);

  const resetAll = useCallback(() => {
    if (!window.confirm("Clear the whole draft?")) return;
    setDraft(EMPTY_DRAFT);
  }, []);

  const buildAnother = useCallback(() => {
    // Keep the video, clear timestamps + options, increment a fresh id
    // on next render via generateItemJson.
    setDraft((d) => ({
      ...d,
      start_at_s: null,
      pause_at_s: null,
      caption: d.caption, // keep — usually same match
      options: [...DEFAULT_OPTIONS] as [string, string, string, string],
      correct_index: 0,
    }));
  }, []);

  const frameStep = 1 / fps;

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">Call the Shot · builder</h1>
        <p className="mt-1 text-sm text-text-secondary">
          Find a moment, mark start + pause, copy the TS object, paste it into{" "}
          <code className="rounded bg-ink-800 px-1">web/lib/call-the-shot-data.ts</code>.
        </p>
      </header>

      <div className="flex gap-2">
        <input
          type="text"
          placeholder="YouTube URL or 11-char video ID"
          value={draft.url_input}
          onChange={(e) => setDraft((d) => ({ ...d, url_input: e.target.value }))}
          className="flex-1 rounded-md border border-ink-700 bg-ink-900 px-3 py-2 text-sm"
        />
        <button
          type="button"
          onClick={onLoad}
          className="rounded-md bg-accent px-4 py-2 text-sm font-bold uppercase tracking-wider text-white hover:bg-accent-dim"
        >
          Load
        </button>
      </div>

      <div className="relative aspect-video w-full overflow-hidden rounded-lg border border-ink-700 bg-black">
        <div id={containerId} className="absolute inset-0 h-full w-full" />
        {!draft.video_id && (
          <div className="absolute inset-0 flex items-center justify-center text-sm text-text-muted">
            Load a video to begin.
          </div>
        )}
      </div>

      {draft.video_id && (
        <>
          <div className="rounded-md border border-ink-700 bg-ink-900 p-3 space-y-2 text-sm">
            <div className="flex items-baseline justify-between">
              <div>
                <div className="text-[10px] uppercase tracking-wider text-text-muted">
                  current time
                </div>
                <div className="text-xl font-mono tabular-nums text-text-primary">
                  {formatTime(currentTime)}
                </div>
              </div>
              <div className="flex items-center gap-2 text-xs">
                <span className="text-text-muted">frame step:</span>
                <button
                  type="button"
                  onClick={() => setFps(30)}
                  className={`rounded px-2 py-1 ${fps === 30 ? "bg-accent text-white" : "border border-ink-700 text-text-secondary"}`}
                >
                  30 fps
                </button>
                <button
                  type="button"
                  onClick={() => setFps(60)}
                  className={`rounded px-2 py-1 ${fps === 60 ? "bg-accent text-white" : "border border-ink-700 text-text-secondary"}`}
                >
                  60 fps
                </button>
              </div>
            </div>
            <div className="flex flex-wrap gap-1.5">
              <JogButton label="-1s" onClick={() => seekDelta(-1)} />
              <JogButton label="-0.1s" onClick={() => seekDelta(-0.1)} />
              <JogButton label="-1f" onClick={() => seekDelta(-frameStep)} />
              <button
                type="button"
                onClick={playPause}
                className="rounded-md bg-accent px-4 py-1.5 text-sm font-bold uppercase tracking-wider text-white hover:bg-accent-dim"
              >
                Play / Pause
              </button>
              <JogButton label="+1f" onClick={() => seekDelta(frameStep)} />
              <JogButton label="+0.1s" onClick={() => seekDelta(0.1)} />
              <JogButton label="+1s" onClick={() => seekDelta(1)} />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <MarkRow
              label="start_at_s"
              value={draft.start_at_s}
              onMark={markStart}
              onClear={() => setDraft((d) => ({ ...d, start_at_s: null }))}
            />
            <MarkRow
              label="pause_at_s"
              value={draft.pause_at_s}
              onMark={markPause}
              onClear={() => setDraft((d) => ({ ...d, pause_at_s: null }))}
            />
          </div>

          <button
            type="button"
            disabled={draft.start_at_s === null || draft.pause_at_s === null}
            onClick={preview}
            className="w-full rounded-md border border-accent/40 bg-accent/10 px-4 py-2 text-sm font-bold uppercase tracking-wider text-accent hover:bg-accent/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Preview: play {formatTime(draft.start_at_s)} → pause {formatTime(draft.pause_at_s)}
          </button>

          <div className="space-y-2">
            <label className="block text-xs uppercase tracking-wider text-text-muted">
              Caption
            </label>
            <input
              type="text"
              placeholder="e.g. Sinner vs Alcaraz · Wimbledon 2025 final"
              value={draft.caption}
              onChange={(e) => setDraft((d) => ({ ...d, caption: e.target.value }))}
              className="w-full rounded-md border border-ink-700 bg-ink-900 px-3 py-2 text-sm"
            />
          </div>

          <div className="space-y-2">
            <label className="block text-xs uppercase tracking-wider text-text-muted">
              Options (pick the correct one)
            </label>
            <div className="space-y-1.5">
              {draft.options.map((opt, i) => (
                <label
                  key={i}
                  className="flex items-center gap-2 rounded-md border border-ink-700 bg-ink-900 px-3 py-2"
                >
                  <input
                    type="radio"
                    name="correct"
                    checked={draft.correct_index === i}
                    onChange={() => setDraft((d) => ({ ...d, correct_index: i as 0 | 1 | 2 | 3 }))}
                  />
                  <input
                    type="text"
                    value={opt}
                    onChange={(e) => setDraft((d) => {
                      const next = [...d.options] as [string, string, string, string];
                      next[i] = e.target.value;
                      return { ...d, options: next };
                    })}
                    className="flex-1 bg-transparent text-sm outline-none"
                  />
                </label>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-baseline justify-between">
              <label className="text-xs uppercase tracking-wider text-text-muted">
                Generated item
              </label>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={buildAnother}
                  className="text-xs font-medium text-accent hover:text-accent-dim"
                >
                  Build another →
                </button>
                <button
                  type="button"
                  onClick={resetAll}
                  className="text-xs font-medium text-red-400 hover:text-red-300"
                >
                  Reset all
                </button>
              </div>
            </div>
            <pre className="overflow-x-auto rounded-md border border-ink-700 bg-ink-900 p-3 text-xs leading-relaxed text-text-primary">
              {itemJson}
            </pre>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={saveItem}
                disabled={saveState === "saving"}
                className="flex-1 rounded-md bg-accent px-4 py-2 text-sm font-bold uppercase tracking-wider text-white hover:bg-accent-dim disabled:opacity-60"
              >
                {saveState === "saving" ? "Saving…" :
                 saveState === "saved" ? "Saved ✓" :
                 "Save to library"}
              </button>
              <button
                type="button"
                onClick={copyJson}
                className="rounded-md border border-ink-700 px-4 py-2 text-sm font-medium text-text-secondary hover:bg-ink-800"
                title="Copy the TS snippet — fallback if the API write fails"
              >
                {copyOk ? "Copied ✓" : "Copy JSON"}
              </button>
            </div>
            {saveState === "error" && saveError && (
              <div className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-700">
                {saveError}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}


function JogButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-md border border-ink-700 bg-ink-900 px-3 py-1.5 text-sm font-mono text-text-primary hover:bg-ink-800"
    >
      {label}
    </button>
  );
}


function MarkRow({
  label,
  value,
  onMark,
  onClear,
}: {
  label: string;
  value: number | null;
  onMark: () => void;
  onClear: () => void;
}) {
  return (
    <div className="rounded-md border border-ink-700 bg-ink-900 p-3 space-y-2">
      <div className="text-[10px] uppercase tracking-wider text-text-muted">{label}</div>
      <div className="font-mono tabular-nums text-text-primary">{formatTime(value)}</div>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={onMark}
          className="flex-1 rounded-md bg-accent px-3 py-1.5 text-xs font-bold uppercase tracking-wider text-white hover:bg-accent-dim"
        >
          Mark
        </button>
        <button
          type="button"
          onClick={onClear}
          className="rounded-md border border-ink-700 px-3 py-1.5 text-xs font-medium text-text-secondary hover:bg-ink-800"
        >
          Clear
        </button>
      </div>
    </div>
  );
}
