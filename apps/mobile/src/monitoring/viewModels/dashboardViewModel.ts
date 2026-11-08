import { sortParcels } from "@aylal/domain/parcel-status";
import { describeFreshness, type Freshness } from "../staleness";

export interface StatusRow {
  parcel_id: string;
  name: string;
  color: string;
  reason_key: string;
  computed_at: string;
  imagery_reliability: string;
  contributors: number;
}

export interface DashboardWeather {
  fetched_at: string | null;
  [k: string]: unknown;
}

export interface DashboardParcel {
  parcelId: string;
  name: string;
  color: string;
  reasonKey: string;
  imageryLow: boolean;
  contributors: number;
}

export interface Dashboard {
  state: "ready" | "empty_no_parcel";
  parcels: DashboardParcel[];
  counts: { red: number; orange: number; green: number };
  weather: DashboardWeather;
  freshness: Freshness;
}

/** Overview in one pass: sorted parcels, counters from the listed rows, oldest data date for freshness. */
export function buildDashboard(rows: readonly StatusRow[], weather: DashboardWeather, now: string): Dashboard {
  const counts = { red: 0, orange: 0, green: 0 };
  const items = rows.map((r) => {
    if (r.color === "red" || r.color === "orange" || r.color === "green") counts[r.color] += 1;
    return { id: r.parcel_id, color: r.color, contributors: r.contributors, name: r.name, row: r };
  });
  const parcels = sortParcels(items).map(({ row: r }) => ({
    parcelId: r.parcel_id, name: r.name, color: r.color, reasonKey: r.reason_key,
    imageryLow: r.imagery_reliability === "low", contributors: r.contributors,
  }));
  const dates = [...rows.map((r) => r.computed_at), ...(weather.fetched_at === null ? [] : [weather.fetched_at])];
  const oldest = dates.length === 0 ? null : dates.reduce((a, b) => (Date.parse(a) <= Date.parse(b) ? a : b));
  return {
    state: rows.length === 0 ? "empty_no_parcel" : "ready",
    parcels, counts, weather, freshness: describeFreshness(oldest, now),
  };
}
