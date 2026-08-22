"use client";

import { useEffect, useMemo, useRef } from "react";

import type { MomentumResponse } from "@/lib/api";
import { SectionHeader } from "@/components/SectionHeader";

/**
 * Momentum Wave — the "tide of the match". Positive (green, top) = player1
 * surging, negative (blue, bottom) = player2. Fed by /api/matches/{id}/momentum.
 * See app/services/momentum.py for the model.
 */

const A = "#16A34A"; // player1 — grass green (accent)
const B = "#2563EB"; // player2 — hard-court blue
const GOLD = "#E8890B"; // break marker
const LINE = "rgba(31,42,55,0.22)";
const GRID = "rgba(31,42,55,0.07)";
const SURFACE = "#FFFFFF";

function hexA(hex: string, a: number): string {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}

function surname(full?: string | null): string {
  if (!full) return "";
  return full.trim().split(" ").slice(-1)[0];
}

// Catmull-Rom sampling through node values (node-space x, interpolated y).
function sampleCurve(nodes: number[], per: number): { x: number; y: number }[] {
  const pts: { x: number; y: number }[] = [];
  const n = nodes.length;
  for (let i = 0; i < n - 1; i++) {
    const p0 = nodes[Math.max(0, i - 1)];
    const p1 = nodes[i];
    const p2 = nodes[i + 1];
    const p3 = nodes[Math.min(n - 1, i + 2)];
    for (let t = 0; t < per; t++) {
      const u = t / per;
      const u2 = u * u;
      const u3 = u2 * u;
      const y =
        0.5 *
        (2 * p1 +
          (-p0 + p2) * u +
          (2 * p0 - 5 * p1 + 4 * p2 - p3) * u2 +
          (-p0 + 3 * p1 - 3 * p2 + p3) * u3);
      pts.push({ x: i + u, y });
    }
  }
  pts.push({ x: n - 1, y: nodes[n - 1] });
  return pts;
}

export function MomentumWave({ data }: { data: MomentumResponse }) {
  const holderRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const overlayRef = useRef<HTMLDivElement | null>(null);
  const tipRef = useRef<HTMLDivElement | null>(null);

  const p1 = surname(data.player1?.full_name) || "Player 1";
  const p2 = surname(data.player2?.full_name) || "Player 2";

  // Nodes: prepend a 0 origin so the wave starts dead-even.
  const nodes = useMemo(() => [0, ...data.series.map((s) => s.m)], [data]);
  const curve = useMemo(() => sampleCurve(nodes, 22), [nodes]);
  const N = nodes.length;

  // Top swings for the narrative strip.
  const topSwings = useMemo(
    () =>
      [...data.events]
        .sort((a, b) => Math.abs(b.swing) - Math.abs(a.swing))
        .slice(0, 3)
        .sort((a, b) => a.i - b.i),
    [data],
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    const holder = holderRef.current;
    const overlay = overlayRef.current;
    if (!canvas || !holder || !overlay) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const PADX = 16;
    const PADY = 16;
    let cssW = 0;
    let cssH = 0;
    let raf = 0;

    const nodeToX = () => (nx: number) => PADX + (nx / (N - 1)) * (cssW - 2 * PADX);
    const gameToX = (gi: number) => PADX + ((gi + 1) / (N - 1)) * (cssW - 2 * PADX);
    const valToY = (v: number) => cssH / 2 - (v / 100) * (cssH / 2 - PADY);

    function drawStatic(progress: number) {
      if (!ctx) return;
      const toX = nodeToX();
      ctx.clearRect(0, 0, cssW, cssH);
      const mid = cssH / 2;

      // faint guide lines
      ctx.strokeStyle = GRID;
      ctx.lineWidth = 1;
      for (const f of [0.25, 0.75]) {
        const y = PADY + f * (cssH - 2 * PADY);
        ctx.beginPath();
        ctx.moveTo(PADX, y);
        ctx.lineTo(cssW - PADX, y);
        ctx.stroke();
      }
      // baseline
      ctx.strokeStyle = LINE;
      ctx.setLineDash([4, 5]);
      ctx.beginPath();
      ctx.moveTo(PADX, mid);
      ctx.lineTo(cssW - PADX, mid);
      ctx.stroke();
      ctx.setLineDash([]);

      const count = Math.max(2, Math.floor(curve.length * progress));
      const seg = curve.slice(0, count).map((p) => ({ x: toX(p.x), y: valToY(p.y) }));
      if (seg.length < 2) return;

      const fillSide = (top: boolean, color: string) => {
        ctx.save();
        ctx.beginPath();
        if (top) ctx.rect(0, 0, cssW, mid);
        else ctx.rect(0, mid, cssW, cssH - mid);
        ctx.clip();
        ctx.beginPath();
        ctx.moveTo(seg[0].x, mid);
        for (const p of seg) ctx.lineTo(p.x, p.y);
        ctx.lineTo(seg[seg.length - 1].x, mid);
        ctx.closePath();
        ctx.fillStyle = color;
        ctx.fill();
        ctx.restore();
      };
      const bandSide = (top: boolean, color: string) => {
        ctx.save();
        ctx.beginPath();
        if (top) ctx.rect(0, 0, cssW, mid);
        else ctx.rect(0, mid, cssW, cssH - mid);
        ctx.clip();
        const grad = ctx.createLinearGradient(0, top ? 0 : cssH, 0, mid);
        grad.addColorStop(0, color);
        grad.addColorStop(1, "transparent");
        ctx.beginPath();
        ctx.moveTo(seg[0].x, mid);
        for (const p of seg) ctx.lineTo(p.x, p.y);
        ctx.lineTo(seg[seg.length - 1].x, mid);
        ctx.closePath();
        ctx.globalAlpha = 0.5;
        ctx.fillStyle = grad;
        ctx.fill();
        ctx.globalAlpha = 1;
        ctx.restore();
      };
      fillSide(true, hexA(A, 0.16));
      fillSide(false, hexA(B, 0.14));
      bandSide(true, hexA(A, 0.32));
      bandSide(false, hexA(B, 0.3));

      // curve line
      ctx.beginPath();
      ctx.moveTo(seg[0].x, seg[0].y);
      for (const p of seg) ctx.lineTo(p.x, p.y);
      ctx.strokeStyle = LINE;
      ctx.lineWidth = 2;
      ctx.lineJoin = "round";
      ctx.stroke();

      // endpoint dot
      const last = seg[seg.length - 1];
      const lastVal = curve[count - 1].y;
      ctx.beginPath();
      ctx.arc(last.x, last.y, 5, 0, Math.PI * 2);
      ctx.fillStyle = lastVal >= 0 ? A : B;
      ctx.fill();
      ctx.strokeStyle = SURFACE;
      ctx.lineWidth = 2;
      ctx.stroke();
    }

    function layoutOverlay() {
      if (!overlay) return;
      overlay.innerHTML = "";
      // set dividers where the set number changes
      for (let k = 0; k < data.series.length - 1; k++) {
        if (data.series[k + 1].set !== data.series[k].set) {
          const x = (gameToX(k) + gameToX(k + 1)) / 2;
          const line = document.createElement("div");
          line.style.cssText = `position:absolute;top:6px;bottom:6px;left:${x}px;width:0;border-left:1px dashed rgba(31,42,55,0.28);`;
          const lab = document.createElement("span");
          lab.textContent = `Set ${data.series[k + 1].set}`;
          lab.style.cssText =
            "position:absolute;top:0;left:5px;font-size:9px;letter-spacing:0.08em;text-transform:uppercase;color:#8E96A6;white-space:nowrap;font-family:ui-monospace,monospace;";
          line.appendChild(lab);
          overlay.appendChild(line);
        }
      }
      // break markers on the baseline
      for (const s of data.series) {
        if (!s.is_break) continue;
        const b = document.createElement("div");
        const col = s.winner === 1 ? A : B;
        b.textContent = "⚡";
        b.title = `${s.winner === 1 ? p1 : p2} broke — Set ${s.set} (${s.score})`;
        b.style.cssText = `position:absolute;left:${gameToX(s.i)}px;top:${cssH / 2}px;transform:translate(-50%,-50%);width:18px;height:18px;border-radius:50%;display:grid;place-items:center;font-size:10px;background:#fff;box-shadow:0 0 0 2px #fff;outline:2px solid ${col};color:${col};`;
        overlay.appendChild(b);
      }
    }

    function resize() {
      if (!canvas || !holder) return;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      cssW = holder.clientWidth;
      cssH = canvas.clientHeight;
      canvas.width = Math.round(cssW * dpr);
      canvas.height = Math.round(cssH * dpr);
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
      layoutOverlay();
      drawStatic(lastProgress);
    }

    let lastProgress = 1;
    function animate() {
      const reduce =
        typeof window !== "undefined" &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (reduce) {
        lastProgress = 1;
        drawStatic(1);
        return;
      }
      const dur = 1400;
      const t0 = performance.now();
      const frame = (now: number) => {
        const p = Math.min(1, (now - t0) / dur);
        lastProgress = 1 - Math.pow(1 - p, 3);
        drawStatic(lastProgress);
        if (p < 1) raf = requestAnimationFrame(frame);
      };
      raf = requestAnimationFrame(frame);
    }

    const tip = tipRef.current;
    function readout(clientX: number) {
      if (!canvas || !tip) return;
      const rect = canvas.getBoundingClientRect();
      const x = clientX - rect.left;
      let best = 0;
      let bd = Infinity;
      for (const s of data.series) {
        const d = Math.abs(gameToX(s.i) - x);
        if (d < bd) {
          bd = d;
          best = s.i;
        }
      }
      const s = data.series[best];
      const v = Math.round(s.m);
      const who = v > 4 ? p1 : v < -4 ? p2 : "Even";
      const col = v > 4 ? A : v < -4 ? B : "#5C6473";
      tip.style.opacity = "1";
      tip.style.left = `${Math.min(cssW - 88, Math.max(88, gameToX(s.i)))}px`;
      tip.style.top = `${valToY(s.m) - 12}px`;
      tip.innerHTML =
        `<div style="font-size:10px;letter-spacing:0.05em;opacity:0.7;font-family:ui-monospace,monospace">SET ${s.set} · ${s.score}</div>` +
        `<div style="font-weight:700;font-size:15px;color:${col};margin:1px 0">${v > 0 ? "+" : ""}${v} · ${who}</div>` +
        `<div style="font-size:12px">${label(s.kind, s.winner === 1 ? p1 : p2)}</div>`;
    }
    const onMove = (e: MouseEvent) => readout(e.clientX);
    const onLeave = () => {
      if (tip) tip.style.opacity = "0";
    };
    const onTouch = (e: TouchEvent) => {
      if (e.touches[0]) readout(e.touches[0].clientX);
    };

    canvas.addEventListener("mousemove", onMove);
    canvas.addEventListener("mouseleave", onLeave);
    canvas.addEventListener("touchstart", onTouch, { passive: true });
    canvas.addEventListener("touchmove", onTouch, { passive: true });

    const ro = new ResizeObserver(() => resize());
    ro.observe(holder);
    resize();
    animate();

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      canvas.removeEventListener("mousemove", onMove);
      canvas.removeEventListener("mouseleave", onLeave);
      canvas.removeEventListener("touchstart", onTouch);
      canvas.removeEventListener("touchmove", onTouch);
    };
  }, [data, curve, N, p1, p2]);

  const lead = data.leader === 1 ? p1 : data.leader === 2 ? p2 : null;
  const leadColor = data.leader === 1 ? A : data.leader === 2 ? B : "#5C6473";
  const live = data.status === "live" || data.status === "suspended";

  return (
    <section>
      <SectionHeader
        title="Momentum"
        subtitle={live ? "Who has the wind at their back — live" : "The tide of the match"}
      />
      <div className="mt-2 overflow-hidden rounded-lg border border-ink-700 bg-ink-900 shadow-card">
        {/* header: players + current read */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-ink-700 px-4 py-3">
          <div className="flex items-center gap-4 text-sm">
            <span className="flex items-center gap-1.5 font-semibold">
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: A }} />
              {p1}
            </span>
            <span className="flex items-center gap-1.5 font-semibold">
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: B }} />
              {p2}
            </span>
          </div>
          {lead && (
            <span className="text-sm font-semibold" style={{ color: leadColor }}>
              {lead} {live ? "surging" : "closed with momentum"} ·{" "}
              <span className="tabular-nums">
                {data.final > 0 ? "+" : ""}
                {Math.round(data.final)}
              </span>
            </span>
          )}
        </div>

        {/* wave */}
        <div className="relative px-2 pt-2" ref={holderRef}>
          <canvas
            ref={canvasRef}
            className="block h-[260px] w-full touch-pan-y sm:h-[300px]"
            aria-label={`Momentum wave: ${p1} vs ${p2}`}
          />
          <div ref={overlayRef} className="pointer-events-none absolute inset-0" />
          <span
            className="pointer-events-none absolute left-3 top-2 font-mono text-[10px] uppercase tracking-wide"
            style={{ color: A }}
          >
            ▲ {p1}
          </span>
          <span
            className="pointer-events-none absolute bottom-2 left-3 font-mono text-[10px] uppercase tracking-wide"
            style={{ color: B }}
          >
            ▼ {p2}
          </span>
          <div
            ref={tipRef}
            className="pointer-events-none absolute z-10 min-w-[150px] max-w-[230px] -translate-x-1/2 rounded-lg px-3 py-2 leading-snug text-white opacity-0 shadow-lg transition-opacity"
            style={{ background: "#1F2A37" }}
          />
        </div>

        {/* legend + key swings */}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-ink-700 px-4 py-2.5 text-xs text-text-secondary">
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-5 rounded-sm" style={{ background: A }} /> {p1} momentum
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-5 rounded-sm" style={{ background: B }} /> {p2} momentum
          </span>
          <span className="flex items-center gap-1" style={{ color: GOLD }}>
            ⚡ break of serve
          </span>
        </div>

        {topSwings.length > 0 && (
          <ul className="divide-y divide-ink-700/60 border-t border-ink-700">
            {topSwings.map((e) => {
              const who = e.winner === 1 ? p1 : p2;
              const up = e.swing >= 0;
              return (
                <li key={e.i} className="flex items-center gap-3 px-4 py-2 text-sm">
                  <span className="w-20 shrink-0 font-mono text-[11px] text-text-muted">
                    Set {e.set} · {e.score}
                  </span>
                  <span className="flex-1 text-text-primary">{label(e.kind, who)}</span>
                  <span
                    className="shrink-0 font-mono text-xs font-semibold tabular-nums"
                    style={{ color: up ? A : B }}
                  >
                    {up ? "▲ +" : "▼ "}
                    {Math.round(Math.abs(e.swing))}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}

function label(kind: string, who: string): string {
  if (kind.startsWith("set")) {
    const tb = kind.includes("tb") ? " tiebreak" : "";
    return kind.includes("break")
      ? `${who} breaks to take the${tb ? tb : ""} set`
      : `${who} closes out the${tb ? tb : ""} set`;
  }
  switch (kind) {
    case "break_back":
      return `${who} breaks straight back`;
    case "break":
      return `${who} breaks serve`;
    case "hold_save_mp":
      return `${who} saves match point and holds`;
    case "hold_save_sp":
      return `${who} saves set point and holds`;
    case "hold_save_bp":
      return `${who} saves break point and holds`;
    default:
      return `${who} holds serve`;
  }
}
