export interface RainMethod {
  method: string;
  params: Record<string, number>;
}

/** Effective rain from a referential method only; greenhouse ignores rain; no default fraction. */
export function effectiveRain(i: { rain_mm: number; method: RainMethod | null; greenhouse: boolean }): {
  rain_eff_mm: number | null; unavailable_reason?: string; rain_source?: string;
} {
  if (i.greenhouse) return { rain_eff_mm: 0, rain_source: "ignored_greenhouse" };
  if (!(i.rain_mm >= 0)) return { rain_eff_mm: null, unavailable_reason: "no_weather" };
  if (i.method && i.method.method === "fraction" && typeof i.method.params?.fraction === "number") {
    return { rain_eff_mm: i.rain_mm * i.method.params.fraction };
  }
  return { rain_eff_mm: null, unavailable_reason: "no_effective_rain_method" };
}
