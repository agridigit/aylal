/** Per crop and stage weather thresholds (reference data validated by agronomy; tests use fixtures only). */
export interface CropWeatherThresholds {
  crop_slug: string;
  stage_key: string;
  frost_c: number | null;
  chergui_tmax_c: number;
  chergui_rh_max_pct: number;
  chergui_wind_kmh: number;
  heavy_rain_mm_24h: number;
  strong_wind_kmh: number;
  source?: string;
}

/** The row for the pair, or null: an unknown pair never gets a default value. */
export function thresholdsFor(
  rows: readonly CropWeatherThresholds[],
  cropSlug: string,
  stageKey: string,
): CropWeatherThresholds | null {
  return rows.find((r) => r.crop_slug === cropSlug && r.stage_key === stageKey) ?? null;
}
