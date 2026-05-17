import { Link } from "expo-router";
import { useMemo, useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";

import type { MatchSummary, PlayerSummary } from "@/lib/api";
import { formatRound, formatSetScore, roundDepth } from "@/lib/format";

const MAIN_DRAW_MIN_DEPTH = 40;
const COL_WIDTH = 200;
const CELL_HEIGHT = 56;

// Each round's feeder round — used to display players in draw-position
// order within each cell instead of "winner always on top".
const DEEPER_ROUND: Record<string, string> = {
  F: "SF", SF: "QF", QF: "R16", R16: "R32", R32: "R64", R64: "R128", R128: "R256",
};

type Props = {
  matches: MatchSummary[];
  drawSize?: number | null;
  padPlaceholders?: boolean;
};

export function Bracket({ matches, drawSize, padPlaceholders = false }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <View>
      <Pressable
        onPress={() => setOpen((o) => !o)}
        className="rounded-md border border-ink-700 bg-ink-900 px-3 py-2.5"
      >
        <Text className="text-center text-sm font-semibold text-text-primary">
          {open ? "Hide bracket" : "Show bracket"}
        </Text>
      </Pressable>
      {open && (
        <View className="mt-3">
          <BracketGrid matches={matches} drawSize={drawSize ?? null} padPlaceholders={padPlaceholders} />
        </View>
      )}
    </View>
  );
}

type Cell =
  | { kind: "match"; match: MatchSummary }
  | { kind: "projected"; p1: PlayerSummary | null; p2: PlayerSummary | null }
  | { kind: "tbd" };

type Column = { depth: number; label: string; cells: Cell[] };

function expectedForRound(drawSize: number, depth: number): number {
  const stepsFromFinal = (100 - depth) / 10;
  if (stepsFromFinal < 0) return 0;
  return Math.min(2 ** stepsFromFinal, Math.floor(drawSize / 2));
}

function labelFromDepth(depth: number): string {
  return (
    {
      100: "F", 90: "SF", 80: "QF", 70: "R16", 60: "R32", 50: "R64", 40: "R128", 30: "R256",
    } as Record<number, string>
  )[depth] ?? "—";
}

function winnerOf(m: MatchSummary): PlayerSummary | null {
  if (m.status !== "finished") return null;
  if (m.winner_slot === 1) return m.player1;
  if (m.winner_slot === 2) return m.player2;
  return null;
}

// Fallback sort for past tournaments without Wikipedia bracket data.
function positionalSort(a: MatchSummary, b: MatchSummary): number {
  const aId = a.api_tennis_id ? parseInt(a.api_tennis_id, 10) : NaN;
  const bId = b.api_tennis_id ? parseInt(b.api_tennis_id, 10) : NaN;
  if (!Number.isNaN(aId) && !Number.isNaN(bId)) return aId - bId;
  const at = a.scheduled_at ? new Date(a.scheduled_at).getTime() : 0;
  const bt = b.scheduled_at ? new Date(b.scheduled_at).getTime() : 0;
  if (at !== bt) return at - bt;
  return a.id - b.id;
}

function buildColumns(
  matches: MatchSummary[],
  drawSize: number | null,
  padPlaceholders: boolean,
): Column[] {
  // Mirror of web/components/Bracket.tsx — two placement strategies
  // picked per-render based on whether the data carries Wikipedia-
  // derived bracket_position. See that file for full rationale.
  const byDepth = new Map<number, MatchSummary[]>();
  for (const m of matches) {
    const d = roundDepth(m.round);
    if (d < MAIN_DRAW_MIN_DEPTH) continue;
    if (!byDepth.has(d)) byDepth.set(d, []);
    byDepth.get(d)!.push(m);
  }
  const haveStructure = matches.some((m) => m.bracket_position !== null);

  const depths = new Set(byDepth.keys());
  if (padPlaceholders && depths.size > 0) {
    const minDepth = Math.min(...depths);
    for (let d = minDepth; d <= 100; d += 10) depths.add(d);
  }

  const cols: Column[] = [];
  let prevExpected = 0;
  for (const depth of [...depths].sort((a, b) => a - b)) {
    const ms = byDepth.get(depth) ?? [];
    let expected: number;
    if (drawSize) expected = expectedForRound(drawSize, depth);
    else if (prevExpected === 0) {
      const maxPos = Math.max(0, ms.length, ...ms.map((m) => (m.bracket_position ?? 0) + 1));
      expected = Math.max(maxPos, 1);
    } else expected = Math.max(1, Math.ceil(prevExpected / 2));
    expected = Math.max(
      expected,
      ms.length,
      ...ms.map((m) => (m.bracket_position ?? 0) + 1),
    );

    const cells: Cell[] = Array.from({ length: expected }, () => ({ kind: "tbd" }));
    if (haveStructure) {
      for (const m of ms) {
        const idx = m.bracket_position ?? -1;
        if (idx >= 0 && idx < cells.length) {
          cells[idx] = { kind: "match", match: m };
        }
      }
    } else {
      const sorted = [...ms].sort(positionalSort);
      for (let i = 0; i < Math.min(sorted.length, cells.length); i++) {
        cells[i] = { kind: "match", match: sorted[i] };
      }
    }
    cols.push({
      depth,
      label: formatRound(ms[0]?.round ?? null) || labelFromDepth(depth),
      cells,
    });
    prevExpected = expected;
  }

  if (padPlaceholders) projectWinnersForward(cols);
  return cols;
}

function projectWinnersForward(cols: Column[]): void {
  for (let ci = 0; ci < cols.length - 1; ci++) {
    const cur = cols[ci];
    const next = cols[ci + 1];
    for (let pos = 0; pos < cur.cells.length; pos++) {
      const cell = cur.cells[pos];
      if (cell.kind !== "match") continue;
      const winner = winnerOf(cell.match);
      if (!winner) continue;
      const nextPos = Math.floor(pos / 2);
      if (nextPos >= next.cells.length) continue;
      const target = next.cells[nextPos];
      if (target.kind === "match") continue;
      const isP1 = pos % 2 === 0;
      const existingP1 = target.kind === "projected" ? target.p1 : null;
      const existingP2 = target.kind === "projected" ? target.p2 : null;
      next.cells[nextPos] = {
        kind: "projected",
        p1: isP1 ? winner : existingP1,
        p2: isP1 ? existingP2 : winner,
      };
    }
  }
}

export function BracketGrid({
  matches,
  drawSize,
  padPlaceholders,
}: {
  matches: MatchSummary[];
  drawSize: number | null;
  padPlaceholders: boolean;
}) {
  const cols = buildColumns(matches, drawSize, padPlaceholders);
  const feederIdx = useMemo(() => {
    const m = new Map<string, MatchSummary>();
    for (const x of matches) {
      if (x.bracket_position !== null && x.round) {
        m.set(`${x.round.toUpperCase()}|${x.bracket_position}`, x);
      }
    }
    return m;
  }, [matches]);
  if (cols.length === 0) return null;

  const tallest = Math.max(...cols.map((c) => c.cells.length));
  const gridHeight = Math.max(tallest, 1) * (CELL_HEIGHT + 8) + 24;
  const hasProjections = cols.some((c) => c.cells.some((cell) => cell.kind === "projected"));

  return (
    <View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        <View className="flex-row gap-2 pb-2" style={{ height: gridHeight }}>
          {cols.map((col) => (
            <View key={col.depth} style={{ width: COL_WIDTH }}>
              <Text className="mb-2 text-center text-[10px] font-bold uppercase tracking-wider text-text-muted">
                {col.label} · {col.cells.length}
              </Text>
              <View className="flex-1 justify-center gap-2">
                {col.cells.map((cell, i) => (
                  <CellRender key={`${col.depth}-${i}`} cell={cell} feederIdx={feederIdx} />
                ))}
              </View>
            </View>
          ))}
        </View>
      </ScrollView>
      {hasProjections && (
        <Text className="mt-1 text-[10px] italic text-text-muted">
          Dashed cells are projected from previous-round winners using draw position.
        </Text>
      )}
    </View>
  );
}

function CellRender({
  cell,
  feederIdx,
}: {
  cell: Cell;
  feederIdx: Map<string, MatchSummary>;
}) {
  if (cell.kind === "match") return <MatchCell match={cell.match} feederIdx={feederIdx} />;
  if (cell.kind === "projected") return <ProjectedCell p1={cell.p1} p2={cell.p2} />;
  return <PlaceholderCell />;
}

function shouldSwapToFeederOrder(
  match: MatchSummary,
  feederIdx: Map<string, MatchSummary>,
): boolean {
  if (match.bracket_position == null || !match.round) return false;
  const deeper = DEEPER_ROUND[match.round.toUpperCase()];
  if (!deeper) return false;
  const topFeeder = feederIdx.get(`${deeper}|${2 * match.bracket_position}`);
  if (!topFeeder) return false;
  const topWinner =
    topFeeder.winner_slot === 1 ? topFeeder.player1 :
    topFeeder.winner_slot === 2 ? topFeeder.player2 : null;
  if (!topWinner) return false;
  return match.player2?.slug === topWinner.slug;
}

function MatchCell({
  match,
  feederIdx,
}: {
  match: MatchSummary;
  feederIdx: Map<string, MatchSummary>;
}) {
  const swap = shouldSwapToFeederOrder(match, feederIdx);
  const topPlayer = swap ? match.player2 : match.player1;
  const bottomPlayer = swap ? match.player1 : match.player2;
  const topSeed = swap ? match.player2_seed : match.player1_seed;
  const bottomSeed = swap ? match.player1_seed : match.player2_seed;

  const sets = (match.score?.trim().split(/\s+/) ?? []).slice(0, 5);
  const origP1 = sets.map((s) => s.split("-")[0] ?? "");
  const origP2 = sets.map((s) => s.split("-")[1] ?? "");
  const topSets = swap ? origP2 : origP1;
  const bottomSets = swap ? origP1 : origP2;

  const finished = match.status === "finished";
  const isLive = match.status === "live";
  const isSuspended = match.status === "suspended";
  const topWon = finished && match.winner_slot === (swap ? 2 : 1);
  const bottomWon = finished && match.winner_slot === (swap ? 1 : 2);

  return (
    <Link href={`/matches/${match.id}` as any} asChild>
      <Pressable className="overflow-hidden rounded-md border border-ink-700 bg-ink-900">
        <Row
          name={topPlayer?.full_name ?? "TBD"}
          seed={topSeed}
          sets={topSets}
          bold={topWon}
          dim={bottomWon}
          winner={topWon}
        />
        <View className="h-px bg-ink-700" style={{ opacity: 0.6 }} />
        <Row
          name={bottomPlayer?.full_name ?? "TBD"}
          seed={bottomSeed}
          sets={bottomSets}
          bold={bottomWon}
          dim={topWon}
          winner={bottomWon}
        />
        {isLive && (
          <View className="bg-accent/10 px-2 py-0.5">
            <Text className="text-center text-[9px] font-bold uppercase tracking-wider text-accent">
              Live
            </Text>
          </View>
        )}
        {isSuspended && (
          <View className="px-2 py-0.5" style={{ backgroundColor: "rgba(251, 191, 36, 0.15)" }}>
            <Text className="text-center text-[9px] font-bold uppercase tracking-wider" style={{ color: "#fbbf24" }}>
              Suspended
            </Text>
          </View>
        )}
      </Pressable>
    </Link>
  );
}

function PlaceholderCell() {
  return (
    <View className="overflow-hidden rounded-md border border-dashed border-ink-700 bg-ink-900" style={{ opacity: 0.5 }}>
      <PlaceholderRow />
      <View className="h-px bg-ink-700" style={{ opacity: 0.3 }} />
      <PlaceholderRow />
    </View>
  );
}

function PlaceholderRow() {
  return (
    <View className="px-2 py-1.5">
      <Text className="text-xs italic text-text-muted">TBD</Text>
    </View>
  );
}

function ProjectedCell({ p1, p2 }: { p1: PlayerSummary | null; p2: PlayerSummary | null }) {
  return (
    <View className="overflow-hidden rounded-md border border-dashed border-ink-700 bg-ink-900" style={{ opacity: 0.75 }}>
      <ProjectedRow player={p1} />
      <View className="h-px bg-ink-700" style={{ opacity: 0.4 }} />
      <ProjectedRow player={p2} />
    </View>
  );
}

function ProjectedRow({ player }: { player: PlayerSummary | null }) {
  return (
    <View className="px-2 py-1.5">
      <Text className="text-xs italic text-text-secondary" numberOfLines={1}>
        {player?.full_name ?? "TBD"}
      </Text>
    </View>
  );
}

function Row({
  name,
  seed,
  sets,
  bold,
  dim,
  winner,
}: {
  name: string;
  seed?: number | null;
  sets: string[];
  bold: boolean;
  dim: boolean;
  winner: boolean;
}) {
  return (
    <View
      className="flex-row items-center gap-1 px-2 py-1.5"
      style={dim ? { opacity: 0.5 } : undefined}
    >
      <Text
        className={`flex-1 text-xs ${bold ? "font-bold text-text-primary" : "text-text-secondary"}`}
        numberOfLines={1}
      >
        {winner ? "▸ " : ""}
        {seed != null ? <Text className="text-[10px] text-text-muted">[{seed}] </Text> : null}
        {name}
      </Text>
      <View className="flex-row items-center gap-1">
        {sets.map((s, i) => (
          <Text
            key={i}
            className={`w-3 text-right text-[11px] ${bold ? "font-bold text-text-primary" : "text-text-secondary"}`}
          >
            {formatSetScore(s)}
          </Text>
        ))}
      </View>
    </View>
  );
}
