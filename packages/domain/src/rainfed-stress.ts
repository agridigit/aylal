type N = number | null | undefined;

/** Rainfed stress: high at RAW, watch from the referential ratio of RAW, none below (binary without ratio). */
export function stressLevel(i: { depletion_mm: number; raw_mm: N; watch_ratio: N }): {
  stress_level: "none" | "watch" | "high" | null; unavailable_reason?: string;
} {
  if (typeof i.raw_mm !== "number") return { stress_level: null, unavailable_reason: "no_soil_reserve" };
  if (i.depletion_mm >= i.raw_mm) return { stress_level: "high" };
  if (typeof i.watch_ratio === "number" && i.depletion_mm >= i.watch_ratio * i.raw_mm) return { stress_level: "watch" };
  return { stress_level: "none" };
}
