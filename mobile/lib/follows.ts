/**
 * Follow management.
 *
 * Backed by the FastAPI /api/follows endpoint, keyed off the device token.
 *
 * Tournaments require a `tour` discriminator (Rome ATP vs Rome WTA share
 * a slug). Players don't — player slugs are globally unique.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type Follow, type FollowKind, type Tour } from "@/lib/api";

const KEY = ["follows"] as const;

type ToggleArgs = { kind: FollowKind; slug: string; tour?: Tour | null };

function eq(a: Follow, b: ToggleArgs): boolean {
  if (a.kind !== b.kind || a.target_slug !== b.slug) return false;
  if (b.kind === "tournament") {
    return a.target_tour === (b.tour ?? null);
  }
  return true;
}

export function useFollows() {
  const qc = useQueryClient();

  const { data: follows = [], isLoading } = useQuery({
    queryKey: KEY,
    queryFn: () => api<Follow[]>("/api/follows", { authed: true }),
    staleTime: 30_000,
  });

  const optimistic = (next: (prev: Follow[]) => Follow[]) => {
    const prev = qc.getQueryData<Follow[]>(KEY) ?? [];
    qc.setQueryData(KEY, next(prev));
    return prev;
  };

  const send = (method: "POST" | "DELETE", a: ToggleArgs) =>
    api<Follow | { ok: true }>("/api/follows", {
      method,
      authed: true,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kind: a.kind,
        target_slug: a.slug,
        target_tour: a.kind === "tournament" ? a.tour ?? null : null,
      }),
    });

  const add = useMutation({
    mutationFn: (a: ToggleArgs) => send("POST", a),
    onMutate: (a) =>
      optimistic((prev) =>
        prev.some((f) => eq(f, a))
          ? prev
          : [
              ...prev,
              {
                kind: a.kind,
                target_slug: a.slug,
                target_tour: a.kind === "tournament" ? a.tour ?? null : null,
              },
            ],
      ),
    onError: (_e, _v, ctx) => qc.setQueryData(KEY, ctx),
    onSettled: () => qc.invalidateQueries({ queryKey: KEY }),
  });

  const remove = useMutation({
    mutationFn: (a: ToggleArgs) => send("DELETE", a),
    onMutate: (a) => optimistic((prev) => prev.filter((f) => !eq(f, a))),
    onError: (_e, _v, ctx) => qc.setQueryData(KEY, ctx),
    onSettled: () => qc.invalidateQueries({ queryKey: KEY }),
  });

  // Pre-computed sets so screens can do O(1) lookups without walking the array.
  const playerSlugs = new Set(
    follows.filter((f) => f.kind === "player").map((f) => f.target_slug),
  );
  // For tournaments we key by `${tour}/${slug}` since the slug alone is ambiguous.
  const tournamentKeys = new Set(
    follows
      .filter((f) => f.kind === "tournament")
      .map((f) => `${f.target_tour ?? ""}/${f.target_slug}`),
  );
  const followedTournaments = follows.filter((f) => f.kind === "tournament");

  return {
    follows,
    isLoading,
    playerSlugs,
    tournamentKeys,
    followedTournaments,
    isFollowing: (kind: FollowKind, slug: string, tour?: Tour | null) =>
      kind === "player"
        ? playerSlugs.has(slug)
        : tournamentKeys.has(`${tour ?? ""}/${slug}`),
    toggle: (kind: FollowKind, slug: string, tour?: Tour | null) => {
      const args: ToggleArgs = { kind, slug, tour };
      const isOn = follows.some((f) => eq(f, args));
      (isOn ? remove : add).mutate(args);
    },
  };
}
