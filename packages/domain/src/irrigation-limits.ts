/** F4 caps (G4). Shared vectors: vectors/f4_limits.json. Mirror: services/api/app/domain/irrigation_limits.py. */
export const LIMITS = {
  pageDefault: 50,
  pageMax: 100,
  syncBatch: 100,
  windowMonths: 24,
  points: 400,
  jobsPerFarm: 5,
  sectors: 50,
  systemVersions: 50,
  eventsPerDaySector: 24,
  durationMin: 1440,
  volumeM3PerHa: 1000,
  backdateDays: 400,
  waterAnalyses: 50,
  ecMax: 100,
} as const;

type Check = (v: number) => boolean;
const between = (lo: number, hi: number): Check => (v) => v >= lo && v <= hi;

const RULES: Record<string, Check> = {
  sectors: between(1, LIMITS.sectors),
  system_versions: between(0, LIMITS.systemVersions),
  events_per_day_sector: between(0, LIMITS.eventsPerDaySector),
  duration_min: between(1, LIMITS.durationMin),
  volume_m3_per_ha: between(0, LIMITS.volumeM3PerHa),
  backdate_days: between(0, LIMITS.backdateDays),
  water_analyses: between(0, LIMITS.waterAnalyses),
  ec_ds_m: (v) => v > 0 && v <= LIMITS.ecMax,
  sync_batch: between(0, LIMITS.syncBatch),
  limit: between(1, LIMITS.pageMax),
  window_months: between(0, LIMITS.windowMonths),
  points: between(0, LIMITS.points),
  jobs_per_farm: between(0, LIMITS.jobsPerFarm),
};

export function withinLimit(rule: string, value: number): boolean {
  const c = RULES[rule];
  return c ? c(value) : false;
}
