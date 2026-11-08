/** F3 caps (G4). Shared vectors: vectors/f3_limits.json. Mirror: services/api/app/domain/monitoring_limits.py. */
export const LIMITS = {
  pageDefault: 50,
  pageMax: 100,
  seriesMonths: 24,
  seriesPoints: 400,
  comparePoints: 200,
  weatherHorizonDays: 8,
  alertsPerFarm: 1000,
  alertsPerParcel: 20,
  zonesPerParcel: 5,
  zonesPerFarm: 200,
  polygonVertices: 200,
  noteChars: 500,
  photoBytes: 3 * 1024 * 1024,
  observationsPerZone: 20,
  observationsPerFarmYear: 2000,
  syncBatch: 100,
  reprocessPerParcelDay: 3,
  imageryJobsPerFarm: 5,
  rasterBytes: 500 * 1024 * 1024,
  initWindowMonths: 12,
} as const;

const MAX_COUNT: Record<string, number> = {
  series_months: LIMITS.seriesMonths,
  series_points: LIMITS.seriesPoints,
  compare_points: LIMITS.comparePoints,
  alerts_per_farm: LIMITS.alertsPerFarm,
  alerts_per_parcel: LIMITS.alertsPerParcel,
  zones_per_parcel: LIMITS.zonesPerParcel,
  zones_per_farm: LIMITS.zonesPerFarm,
  polygon_vertices: LIMITS.polygonVertices,
  note_chars: LIMITS.noteChars,
  photo_bytes: LIMITS.photoBytes,
  observations_per_zone: LIMITS.observationsPerZone,
  observations_per_farm_year: LIMITS.observationsPerFarmYear,
  sync_batch: LIMITS.syncBatch,
  reprocess_per_parcel_day: LIMITS.reprocessPerParcelDay,
  imagery_jobs_per_farm: LIMITS.imageryJobsPerFarm,
  raster_bytes: LIMITS.rasterBytes,
  init_window_months: LIMITS.initWindowMonths,
};

/** True when `value` respects the cap named `rule`; an unknown rule is refused. */
export function withinLimit(rule: string, value: number): boolean {
  if (typeof value !== "number" || !Number.isFinite(value)) return false;
  if (rule === "limit") return value >= 1 && value <= LIMITS.pageMax;
  if (rule === "weather_horizon_days") return value === LIMITS.weatherHorizonDays;
  const max = MAX_COUNT[rule];
  return max !== undefined && value >= 0 && value <= max;
}
