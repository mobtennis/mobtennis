export function formatScore(score: string | null): string[] {
  if (!score) return [];
  return score.trim().split(/\s+/);
}

// Convert digits inside parentheses to Unicode superscript so a tiebreak
// like "7(6)" renders as "7⁶". Tennis convention. The backend emits the
// (N) form because it's unambiguous to debug; presentation is the web's job.
const SUP_DIGITS: Record<string, string> = {
  "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
  "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
};

export function formatSetScore(part: string): string {
  return part.replace(/\((\d+)\)/g, (_, digits: string) =>
    digits.split("").map((d) => SUP_DIGITS[d] ?? d).join(""),
  );
}

// api-tennis ships the round as "<TOURNAMENT NAME> - <ROUND>" (e.g.
// "ATP Rome - 1/64-finals"). Cards live inside tournament-grouped containers,
// so the prefix is redundant noise. We also abbreviate to the standard short
// form (R128/R64/QF/SF/F) so it fits the cramped right column.
const ROUND_ABBREV: Record<string, string> = {
  "1/128-finals": "R256",
  "1/64-finals": "R128",
  "1/32-finals": "R64",
  "1/16-finals": "R32",
  "1/8-finals": "R16",
  "quarter-finals": "QF",
  "quarterfinals": "QF",
  "qf": "QF",
  "semi-finals": "SF",
  "semifinals": "SF",
  "sf": "SF",
  "final": "F",
  "f": "F",
  "first round": "R1",
  "second round": "R2",
  "third round": "R3",
  "fourth round": "R4",
  "round 1": "R1",
  "round 2": "R2",
  "round 3": "R3",
  "round 4": "R4",
  "qualification": "Q",
};

export function formatRound(round: string | null): string {
  if (!round) return "";
  const lastDash = round.lastIndexOf(" - ");
  const tail = (lastDash >= 0 ? round.slice(lastDash + 3) : round).trim();
  return ROUND_ABBREV[tail.toLowerCase()] ?? tail;
}

// "Path to the trophy" rounds — what's worth surfacing for archived editions
// where the full bracket would be noise. F, SF, QF = at most 7 matches.
export function isDeepRound(round: string | null): boolean {
  const r = formatRound(round);
  return r === "F" || r === "SF" || r === "QF";
}

// Higher = later in the tournament. Mirrors backend/app/services/rounds.py.
const ROUND_DEPTH: Record<string, number> = {
  F: 100, SF: 90, QF: 80,
  R16: 70, R32: 60, R64: 50, R128: 40, R256: 30,
  Q3: 25, Q2: 20, Q1: 15, Q: 10,
};

export function roundDepth(round: string | null): number {
  const r = formatRound(round);
  return ROUND_DEPTH[r] ?? 0;
}

/**
 * Parse an ISO timestamp from our API as UTC, then return a Date in the
 * browser's local timezone. The backend stores everything in UTC but
 * Pydantic serializes naive datetimes without a 'Z' suffix, which
 * JavaScript's Date constructor then interprets as local time —
 * showing tennis fans in Reykjavik a match "starting at 17:30" when
 * upstream actually meant 17:30 UTC. Append the suffix when missing
 * so toLocaleString renders correctly for every user.
 *
 * Exported so call sites that need a Date object (e.g. for arithmetic
 * comparisons against `Date.now()`) get the same UTC interpretation.
 */
export function parseUtcIso(iso: string): Date {
  const naive = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?$/.test(iso);
  return new Date(naive ? `${iso}Z` : iso);
}

/**
 * True if the given UTC timestamp falls on the user's local "today."
 * Used to keep finished matches on the live view until end-of-day in
 * their timezone — so a match that ended an hour ago is still right
 * there, no need to dig into the bracket.
 */
export function isLocalToday(iso: string | null): boolean {
  if (!iso) return false;
  const d = parseUtcIso(iso);
  const now = new Date();
  return (
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  );
}

export function formatTime(iso: string | null): string {
  if (!iso) return "";
  return parseUtcIso(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function formatDate(iso: string | null): string {
  if (!iso) return "";
  return parseUtcIso(iso).toLocaleDateString([], { month: "short", day: "numeric" });
}

export function formatRelative(iso: string): string {
  const d = parseUtcIso(iso);
  const now = Date.now();
  const diff = (now - d.getTime()) / 1000;
  if (diff < 60) return "now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
  return d.toLocaleDateString([], { month: "short", day: "numeric" });
}

export function flagEmoji(iso3: string | null): string {
  if (!iso3) return "";
  // Approximate map of common ISO3 → ISO2 country codes for flag emoji.
  // Tennis player nationalities are well-covered by this set.
  const map: Record<string, string> = {
    USA: "US", GBR: "GB", ESP: "ES", FRA: "FR", ITA: "IT", GER: "DE",
    SUI: "CH", AUT: "AT", SRB: "RS", CRO: "HR", RUS: "RU", BLR: "BY",
    POL: "PL", CZE: "CZ", SVK: "SK", BUL: "BG", GRE: "GR", DEN: "DK",
    SWE: "SE", NOR: "NO", FIN: "FI", NED: "NL", BEL: "BE", POR: "PT",
    UKR: "UA", AUS: "AU", NZL: "NZ", JPN: "JP", CHN: "CN", KOR: "KR",
    TPE: "TW", HKG: "HK", IND: "IN", THA: "TH", KAZ: "KZ", UZB: "UZ",
    CAN: "CA", MEX: "MX", BRA: "BR", ARG: "AR", CHI: "CL", COL: "CO",
    PER: "PE", URU: "UY", RSA: "ZA", TUN: "TN", EGY: "EG", MAR: "MA",
    ISR: "IL", TUR: "TR", LIB: "LB", HUN: "HU", ROU: "RO", LAT: "LV",
    LTU: "LT", EST: "EE", SLO: "SI", BIH: "BA", MNE: "ME", MDA: "MD",
    GEO: "GE", ARM: "AM", AZE: "AZ", IRL: "IE", ISL: "IS", LUX: "LU",
  };
  const iso2 = map[iso3.toUpperCase()];
  if (!iso2) return "";
  return iso2
    .split("")
    .map((c) => String.fromCodePoint(0x1f1e6 + c.charCodeAt(0) - 65))
    .join("");
}

export function tournamentColor(category: string): string {
  if (category === "grand_slam") return "bg-amber-100 text-amber-800 border-amber-200";
  if (category.includes("1000")) return "bg-rose-100 text-rose-800 border-rose-200";
  if (category.includes("500")) return "bg-sky-100 text-sky-800 border-sky-200";
  if (category.includes("250")) return "bg-emerald-100 text-emerald-800 border-emerald-200";
  return "bg-ink-800 text-text-secondary border-ink-700";
}

export function surfaceColor(surface: string | null): string {
  if (!surface) return "text-text-secondary";
  if (surface === "grass") return "text-court-grass";
  if (surface === "clay") return "text-court-clay";
  if (surface === "hard") return "text-court-hard";
  if (surface === "carpet") return "text-court-carpet";
  return "text-text-secondary";
}
