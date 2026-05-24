/**
 * Heartbeat-alert relay → Resend email.
 *
 * UptimeRobot and Healthchecks.io both fire webhooks at this endpoint
 * when a monitor goes down. We forward to Resend so the alert lands in
 * the inbox without paying for either service's premium-tier email.
 *
 * Why this lives on Vercel (and not on the backend): when the backend
 * is the thing that's down, a relay hosted on the backend can't fire.
 * Vercel's edge keeps this endpoint reachable as long as DNS + the
 * Next.js deployment are alive — strictly more independent failure
 * domains than the backend itself.
 *
 * Auth: shared secret in the query string (`?secret=...`). Webhooks
 * don't carry signatures we can verify uniformly across providers, so
 * a secret URL is the simplest practical guard against spam.
 *
 * Required env (set in Vercel dashboard):
 *   RESEND_API_KEY        — from resend.com/api-keys
 *   RESEND_FROM_EMAIL     — e.g. "Mob Tennis Alerts <onboarding@resend.dev>"
 *                           (or "alerts@mob.tennis" once the domain is verified)
 *   ALERT_TO_EMAIL        — recipient (must be the verified Resend account
 *                           email until a sending domain is verified)
 *   RELAY_SECRET          — long random string; share with the webhook URLs
 */

import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

async function sendEmail(subject: string, text: string): Promise<Response> {
  const apiKey = process.env.RESEND_API_KEY;
  const from = process.env.RESEND_FROM_EMAIL || "onboarding@resend.dev";
  const to = process.env.ALERT_TO_EMAIL;
  if (!apiKey || !to) {
    return new Response("RESEND_API_KEY or ALERT_TO_EMAIL not set", { status: 500 });
  }
  return fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ from, to: [to], subject, text }),
  });
}

function isAuthorized(req: Request): boolean {
  const expected = process.env.RELAY_SECRET;
  if (!expected) return false;
  const url = new URL(req.url);
  return url.searchParams.get("secret") === expected;
}

export async function GET(req: Request) {
  if (!isAuthorized(req)) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  // `?test=1` sends a one-off probe email so you can verify the wiring
  // end-to-end before pointing live monitors at this URL.
  const url = new URL(req.url);
  if (url.searchParams.get("test") === "1") {
    const r = await sendEmail(
      "Mob Tennis: heartbeat relay test",
      "If you're reading this, Vercel → Resend → your inbox is wired up correctly.",
    );
    if (!r.ok) {
      return NextResponse.json({ error: "resend failed", detail: await r.text() }, { status: 500 });
    }
    return NextResponse.json({ ok: true, sent: true });
  }
  return NextResponse.json({ ok: true, message: "heartbeat relay alive" });
}

export async function POST(req: Request) {
  if (!isAuthorized(req)) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const url = new URL(req.url);
  const source = url.searchParams.get("source") || "monitor";

  // Webhooks come in many shapes. Try JSON first, fall back to text /
  // form-encoded — the body is for human eyes anyway.
  let body: string;
  const ctype = req.headers.get("content-type") || "";
  try {
    if (ctype.includes("application/json")) {
      body = JSON.stringify(await req.json(), null, 2);
    } else if (ctype.includes("application/x-www-form-urlencoded")) {
      const form = await req.formData();
      const obj: Record<string, FormDataEntryValue> = {};
      for (const [k, v] of form.entries()) obj[k] = v;
      body = JSON.stringify(obj, null, 2);
    } else {
      body = await req.text();
    }
  } catch (e) {
    body = `(failed to read body: ${(e as Error).message})`;
  }

  const subject = `Mob Tennis heartbeat: ${source} alert`;
  const text = `Source: ${source}\nTime: ${new Date().toISOString()}\n\n${body}`;

  const r = await sendEmail(subject, text);
  if (!r.ok) {
    const detail = await r.text();
    console.error("resend failed:", detail);
    return NextResponse.json({ error: "resend failed", detail }, { status: 500 });
  }
  return NextResponse.json({ ok: true });
}
