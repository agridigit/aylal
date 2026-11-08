type N = number | null | undefined;

/** FAO-29: LR = ECw / (5 ECe_max - ECw), none up to the tolerance threshold, capped by leaching_max. */
export function leachingFraction(i: { ecw_ds_m: number; ece_threshold_ds_m: N; ece_max_ds_m: N; leaching_max: N }): {
  leaching_fraction: number | null; unavailable_reason?: string;
} {
  if (typeof i.ece_max_ds_m !== "number" || typeof i.leaching_max !== "number") {
    return { leaching_fraction: null, unavailable_reason: "no_salinity_reference" };
  }
  if (typeof i.ece_threshold_ds_m === "number" && i.ecw_ds_m <= i.ece_threshold_ds_m) return { leaching_fraction: 0 };
  const den = 5 * i.ece_max_ds_m - i.ecw_ds_m;
  if (den <= 0) return { leaching_fraction: i.leaching_max };
  return { leaching_fraction: Math.min(i.leaching_max, i.ecw_ds_m / den) };
}

export function grossNeed(i: { net_need_mm: number; leaching_fraction: number }): { gross_need_mm: number } {
  return { gross_need_mm: i.net_need_mm / (1 - i.leaching_fraction) };
}
