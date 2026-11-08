import { createHash } from "node:crypto";
import type { CropWeatherThresholds } from "./weather-thresholds";

export type AlertType = "frost" | "chergui" | "heavy_rain" | "strong_wind";
export type Severity = "info" | "warning" | "critical";

export interface ForecastDay {
  date: string;
  tmin: number;
  tmax: number;
  rain_mm: number;
  wind_kmh: number;
  humidity_pct: number;
}

export interface DayAlert {
  type: AlertType;
  severity: Severity;
  reasonKey: string;
  adviceKey: string | null;
  params: Record<string, number>;
}

/** Frost: at least this many degrees under the threshold is critical, closer is a warning. */
const FROST_CRITICAL_MARGIN_C = 1;
/** Heavy rain: at least this multiple of the threshold is critical. */
const RAIN_CRITICAL_RATIO = 1.5;

/** Alerts of one forecast day for one crop and stage. Without thresholds nothing is produced. */
export function evaluateDay(t: CropWeatherThresholds | null, day: ForecastDay): DayAlert[] {
  if (t === null) return [];
  const out: DayAlert[] = [];
  if (t.frost_c !== null && day.tmin <= t.frost_c) {
    const margin = t.frost_c - day.tmin;
    out.push({
      type: "frost", severity: margin >= FROST_CRITICAL_MARGIN_C ? "critical" : "warning", reasonKey: "alert.frost",
      adviceKey: null, params: { tmin: day.tmin, threshold: t.frost_c },
    });
  }
  if (day.tmax >= t.chergui_tmax_c && day.humidity_pct <= t.chergui_rh_max_pct && day.wind_kmh >= t.chergui_wind_kmh) {
    out.push({
      type: "chergui", severity: "warning", reasonKey: "alert.chergui", adviceKey: null,
      params: { tmax: day.tmax, humidity_pct: day.humidity_pct, wind_kmh: day.wind_kmh },
    });
  }
  if (day.rain_mm >= t.heavy_rain_mm_24h) {
    out.push({
      type: "heavy_rain", severity: day.rain_mm >= t.heavy_rain_mm_24h * RAIN_CRITICAL_RATIO ? "critical" : "warning",
      reasonKey: "alert.heavy_rain", adviceKey: null, params: { rain_mm: day.rain_mm, threshold: t.heavy_rain_mm_24h },
    });
  }
  if (day.wind_kmh > t.strong_wind_kmh) {
    out.push({
      type: "strong_wind", severity: "warning", reasonKey: "alert.strong_wind", adviceKey: "do_not_spray",
      params: { wind_kmh: day.wind_kmh, threshold: t.strong_wind_kmh },
    });
  }
  return out;
}

/** One alert per (farm, parcel, crop, type, forecast day): sha-256 hex of the components. */
export function dedupKey(k: { farmId: string; parcelId: string; cropSlug: string; type: string; forecastDay: string }): string {
  return createHash("sha256").update([k.farmId, k.parcelId, k.cropSlug, k.type, k.forecastDay].join("|")).digest("hex");
}
