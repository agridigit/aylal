import { LIMITS } from "@aylal/domain/monitoring-limits";
import { staleness } from "@aylal/domain/staleness";

export interface WeatherDayRow {
  date: string;
  tmin: number;
  tmax: number;
  rain_mm: number;
  wind_kmh: number;
  humidity_pct: number;
  icon: string;
}

export interface WeatherRecord {
  availability: string;
  reason: string | null;
  fetched_at: string | null;
  days: WeatherDayRow[];
}

export interface WeatherDay {
  date: string;
  tmin: number;
  tmax: number;
  rainMm: number;
  windKmh: number;
  humidityPct: number;
  icon: string;
}

export interface WeatherState {
  state: "ready" | "not_located" | "unavailable";
  days: WeatherDay[];
  fetchedAt: string | null;
  stale: boolean;
}

const EMPTY: WeatherState = { state: "unavailable", days: [], fetchedAt: null, stale: true };

/** Weather screen state read from the local store; no value is ever invented. */
export function createWeatherViewModel(store: { read: (farmId: string) => Promise<WeatherRecord | null> }, now: () => string) {
  return {
    async load(farmId: string): Promise<WeatherState> {
      const rec = await store.read(farmId);
      if (rec === null) return { ...EMPTY };
      const days = rec.days.slice(0, LIMITS.weatherHorizonDays).map((d) => ({
        date: d.date, tmin: d.tmin, tmax: d.tmax, rainMm: d.rain_mm, windKmh: d.wind_kmh, humidityPct: d.humidity_pct, icon: d.icon,
      }));
      const stale = staleness(rec.fetched_at, now()).stale;
      if (rec.reason === "farm_not_located") return { state: "not_located", days: [], fetchedAt: null, stale: true };
      if (rec.availability !== "ok") return { state: "unavailable", days, fetchedAt: rec.fetched_at, stale };
      return { state: "ready", days, fetchedAt: rec.fetched_at, stale };
    },
  };
}
