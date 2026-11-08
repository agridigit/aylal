/** A scene is published only when at least 80 % of the parcel is clear (FR-007); never more than 100 %. */
export const CLOUD_MIN_CLEAR_PCT = 80;

export function isScenePublishable(clearPct: number, minClearPct: number = CLOUD_MIN_CLEAR_PCT): boolean {
  return Number.isFinite(clearPct) && clearPct >= minClearPct && clearPct <= 100;
}

const DAY_MS = 86_400_000;
const dayNumber = (iso: string): number => Date.parse(`${iso.slice(0, 10)}T00:00:00Z`) / DAY_MS;

/** Campaign start: the season start date, otherwise the last 1 September not after `today`. */
export function campaignStart(seasonStartedAt: string | null, today: string): string {
  if (seasonStartedAt) return seasonStartedAt.slice(0, 10);
  const year = Number(today.slice(0, 4));
  const thisYear = `${year}-09-01`;
  return today.slice(0, 10) >= thisYear ? thisYear : `${year - 1}-09-01`;
}

/** Whole days elapsed from the campaign start. */
export function campaignDay(start: string, date: string): number {
  return Math.round(dayNumber(date) - dayNumber(start));
}

export interface VigorSample {
  acquired_on: string;
  vigor: number;
  plant_moisture: number;
}

export interface AlignedVigor {
  day: number;
  vigor: number | null;
  plant_moisture: number | null;
}

function interpolate(pts: readonly { day: number; value: number }[], day: number): number | null {
  const first = pts[0];
  const last = pts[pts.length - 1];
  if (!first || !last || day < first.day || day > last.day) return null;
  for (let i = 0; i < pts.length; i++) {
    const b = pts[i];
    if (!b) continue;
    if (b.day === day) return b.value;
    const a = pts[i - 1];
    if (a && b.day > day && a.day < day) return a.value + ((b.value - a.value) * (day - a.day)) / (b.day - a.day);
  }
  return null;
}

/** Reads a curve on given campaign days: linear interpolation between valid points, never extrapolated, null (never 0) otherwise. */
export function alignToCampaignDays(points: readonly VigorSample[], start: string, days: readonly number[]): AlignedVigor[] {
  const series = (pick: (p: VigorSample) => number) =>
    points
      .filter((p) => Number.isFinite(pick(p)))
      .map((p) => ({ day: campaignDay(start, p.acquired_on), value: pick(p) }))
      .sort((a, b) => a.day - b.day);
  const vig = series((p) => p.vigor);
  const moist = series((p) => p.plant_moisture);
  return days.map((day) => ({ day, vigor: interpolate(vig, day), plant_moisture: interpolate(moist, day) }));
}
