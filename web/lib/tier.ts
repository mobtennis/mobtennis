// Mirror of the backend's tier_weight() — keeps the live page's sort order
// aligned with the tournaments index without an extra round-trip.
const TIER_WEIGHT: Record<string, number> = {
  grand_slam: 0,
  atp_finals: 1,
  wta_finals: 1,
  atp_1000: 2,
  wta_1000: 2,
  atp_500: 3,
  wta_500: 3,
  atp_250: 4,
  wta_250: 4,
  davis_cup: 5,
  bjk_cup: 5,
  challenger: 6,
  itf: 7,
  other: 8,
};

export function tierWeight(category: string | null | undefined): number {
  if (!category) return 99;
  return TIER_WEIGHT[category] ?? 99;
}
