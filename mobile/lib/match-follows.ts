/**
 * Match-follow management. Transient — the backend auto-purges follows when
 * the match ends, so we just refetch on a cadence.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type MatchFollow, type MatchFollowGranularity } from "@/lib/api";

const KEY = ["match-follows"] as const;

export function useMatchFollows() {
  const qc = useQueryClient();

  const { data: follows = [] } = useQuery({
    queryKey: KEY,
    queryFn: () => api<MatchFollow[]>("/api/follows/matches", { authed: true }),
    staleTime: 30_000,
  });

  const optimistic = (next: (prev: MatchFollow[]) => MatchFollow[]) => {
    const prev = qc.getQueryData<MatchFollow[]>(KEY) ?? [];
    qc.setQueryData(KEY, next(prev));
    return prev;
  };

  const add = useMutation({
    mutationFn: ({ matchId, granularity }: { matchId: number; granularity: MatchFollowGranularity }) =>
      api("/api/follows/matches", {
        method: "POST",
        authed: true,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ match_id: matchId, granularity }),
      }),
    onMutate: ({ matchId, granularity }) =>
      optimistic((prev) => {
        const without = prev.filter((f) => f.match_id !== matchId);
        return [...without, { match_id: matchId, granularity }];
      }),
    onError: (_e, _v, ctx) => qc.setQueryData(KEY, ctx),
    onSettled: () => qc.invalidateQueries({ queryKey: KEY }),
  });

  const remove = useMutation({
    mutationFn: ({ matchId }: { matchId: number }) =>
      api("/api/follows/matches", {
        method: "DELETE",
        authed: true,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ match_id: matchId }),
      }),
    onMutate: ({ matchId }) =>
      optimistic((prev) => prev.filter((f) => f.match_id !== matchId)),
    onError: (_e, _v, ctx) => qc.setQueryData(KEY, ctx),
    onSettled: () => qc.invalidateQueries({ queryKey: KEY }),
  });

  return {
    follows,
    getGranularity: (matchId: number): MatchFollowGranularity | null => {
      const f = follows.find((x) => x.match_id === matchId);
      return f ? f.granularity : null;
    },
    follow: (matchId: number, granularity: MatchFollowGranularity = "key_moments") =>
      add.mutate({ matchId, granularity }),
    unfollow: (matchId: number) => remove.mutate({ matchId }),
  };
}
