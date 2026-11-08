import { alignToCampaignDays, type VigorSample } from "@aylal/domain/vigor";

export interface ComparePoint extends VigorSample {
  day_of_campaign: number;
}

export interface YearCompareRecord {
  reference_available: boolean;
  current: ComparePoint[];
  previous: ComparePoint[];
}

export interface CompareRow {
  day: number;
  current: number | null;
  previous: number | null;
}

export type YearCompareState =
  | { state: "ready"; rows: CompareRow[] }
  | { state: "no_reference"; messageKey: "monitoring.compare.no_reference" }
  | { state: "empty" }
  | { state: "unavailable" };

/** Both curves are read on the same campaign days (union of the days of both curves). */
export function createYearCompareViewModel(store: { read: (farmId: string, parcelId: string) => Promise<YearCompareRecord | null> }) {
  return {
    async load(farmId: string, parcelId: string): Promise<YearCompareState> {
      const rec = await store.read(farmId, parcelId);
      if (rec === null) return { state: "unavailable" };
      if (rec.current.length === 0 && rec.previous.length === 0) return { state: "empty" };
      if (!rec.reference_available) return { state: "no_reference", messageKey: "monitoring.compare.no_reference" };
      const days = [...new Set([...rec.current, ...rec.previous].map((p) => p.day_of_campaign))].sort((a, b) => a - b);
      // day_of_campaign is already counted from each year's own start: align on a common origin
      const origin = "2000-01-01";
      const shift = (pts: ComparePoint[]) =>
        pts.map((p) => ({ ...p, acquired_on: new Date(Date.parse(`${origin}T00:00:00Z`) + p.day_of_campaign * 86_400_000).toISOString().slice(0, 10) }));
      const cur = alignToCampaignDays(shift(rec.current), origin, days);
      const prev = alignToCampaignDays(shift(rec.previous), origin, days);
      return { state: "ready", rows: days.map((day, i) => ({ day, current: cur[i]?.vigor ?? null, previous: prev[i]?.vigor ?? null })) };
    },
  };
}
