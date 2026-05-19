import { useQuery } from "@tanstack/react-query";
import { Redirect } from "expo-router";
import { Text } from "react-native";

import { Screen } from "@/components/Screen";
import { api, type DigestDetail } from "@/lib/api";

/** Bounces to the dated archive URL for the latest digest. Keeps the
 * canonical route shape `/digest/[week]` consistent with the web. */
export default function DigestIndexScreen() {
  const { data: digest, isLoading, isError } = useQuery({
    queryKey: ["digest-latest"],
    queryFn: () => api<DigestDetail>("/api/digests/latest"),
    retry: false,
  });

  if (isLoading) {
    return (
      <Screen>
        <Text className="text-center text-text-muted">Loading…</Text>
      </Screen>
    );
  }
  if (isError || !digest) {
    return (
      <Screen>
        <Text className="text-center text-text-muted">No digest available yet.</Text>
      </Screen>
    );
  }
  return <Redirect href={`/digest/${digest.week_start}` as any} />;
}
