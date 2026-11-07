/** F6 caps (G3). Shared vectors: vectors/f6_limits.json. Mirror: services/api/app/domain/operation_limits.py. */
export const LIMITS = {
  pageDefault: 50,
  pageLimit: 200,
  batch: 100,
  parcels: 50,
  productLines: 5,
  noteLength: 500,
  freeProductLength: 80,
  operatorLength: 80,
  textLength: 500,
  exportRows: 10_000,
  exportYears: 5,
  opsPerFarmYear: 20_000,
  plannedCount: 500,
  doseMin: 0.001,
  doseMax: 100_000,
  doseDecimals: 3,
  labelBytes: 3 * 1024 * 1024,
  minPerformedOn: "2000-01-01",
  maxFutureYears: 2,
} as const;

const MAX_COUNT: Record<string, number> = {
  product_lines: LIMITS.productLines,
  batch: LIMITS.batch,
  note_length: LIMITS.noteLength,
  free_product_length: LIMITS.freeProductLength,
  operator_length: LIMITS.operatorLength,
  export_rows: LIMITS.exportRows,
  export_years: LIMITS.exportYears,
  ops_per_farm_year: LIMITS.opsPerFarmYear,
  planned_count: LIMITS.plannedCount,
};

const pad = (n: number) => String(n).padStart(2, "0");

/** Latest accepted `performed_on`: today plus two years (29 February falls back to 28). */
export function latestPerformedOn(today: string): string {
  const [y = 0, m = 0, d = 0] = today.split("-").map(Number);
  const year = y + LIMITS.maxFutureYears;
  const leap = (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0;
  return `${year}-${pad(m)}-${pad(m === 2 && d === 29 && !leap ? 28 : d)}`;
}

/** True when `value` respects the cap named `rule`; an unknown rule is refused. */
export function withinLimit(rule: string, value: number | string, today: string): boolean {
  if (rule === "performed_on") {
    return typeof value === "string" && value >= LIMITS.minPerformedOn && value <= latestPerformedOn(today);
  }
  if (typeof value !== "number" || !Number.isFinite(value)) return false;
  if (rule === "parcels") return value >= 1 && value <= LIMITS.parcels;
  if (rule === "page_limit") return value >= 1 && value <= LIMITS.pageLimit;
  if (rule === "dose") {
    const scaled = value * 10 ** LIMITS.doseDecimals;
    return value >= LIMITS.doseMin - 1e-9 && value <= LIMITS.doseMax && Math.abs(scaled - Math.round(scaled)) < 1e-6;
  }
  const max = MAX_COUNT[rule];
  return max !== undefined && value >= 0 && value <= max;
}
