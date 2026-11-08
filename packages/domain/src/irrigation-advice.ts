import { irrigationMinutes } from "./application-rate";
import { grossNeed } from "./leaching";
import { stressLevel } from "./rainfed-stress";

type N = number | null | undefined;

/** Rain strictly above this many mm on the local day postpones irrigation (CPS section 9). */
export const POSTPONE_RAIN_MM = 10;

export interface AdviceInput {
  irrigated: boolean;
  greenhouse: boolean;
  has_system: boolean;
  system: { efficiency: N; rate_mm_h: N; sectors_count: number } | null;
  depletion_mm: number;
  raw_mm: N;
  rain_mm_today: N;
  leaching_fraction: N;
  stress_watch_ratio: N;
}

export interface AdviceOut {
  kind: "irrigate" | "no_need" | "postpone_rain" | "rainfed_stress" | "unavailable";
  net_need_mm: number | null;
  total_minutes: number | null;
  sectors: { sector_no: number; minutes: number }[];
  stress_level: string | null;
  unavailable_reason: string | null;
}

const base = (kind: AdviceOut["kind"]): AdviceOut => ({
  kind, net_need_mm: null, total_minutes: null, sectors: [], stress_level: null, unavailable_reason: null,
});

export function computeAdvice(i: AdviceInput): AdviceOut {
  if (typeof i.raw_mm !== "number") return { ...base("unavailable"), unavailable_reason: "no_soil_reserve" };
  if (!i.irrigated) {
    const s = stressLevel({ depletion_mm: i.depletion_mm, raw_mm: i.raw_mm, watch_ratio: i.stress_watch_ratio });
    return { ...base("rainfed_stress"), stress_level: s.stress_level };
  }
  if (!i.has_system || !i.system) return { ...base("unavailable"), unavailable_reason: "no_system" };
  if (i.depletion_mm < i.raw_mm) return base("no_need");
  if (!i.greenhouse && typeof i.rain_mm_today === "number" && i.rain_mm_today > POSTPONE_RAIN_MM) return base("postpone_rain");
  const lr = typeof i.leaching_fraction === "number" ? i.leaching_fraction : 0;
  const gross = grossNeed({ net_need_mm: i.depletion_mm, leaching_fraction: lr }).gross_need_mm;
  const m = irrigationMinutes({ net_need_mm: gross, efficiency: i.system.efficiency ?? null, rate_mm_h: i.system.rate_mm_h ?? null }).minutes;
  if (m === null) return { ...base("unavailable"), unavailable_reason: "no_system" };
  const sectors = Array.from({ length: i.system.sectors_count }, (_, k) => ({ sector_no: k + 1, minutes: m }));
  return { ...base("irrigate"), net_need_mm: gross, total_minutes: m * i.system.sectors_count, sectors };
}

export interface CropRow { kc: N; root_depth_m: N; depletion_fraction: N; validated: boolean }
export interface SoilRow { texture_key: string; available_water_mm_per_m: N }

/** Referential gaps -> unavailable with a reason; an unknown texture takes the weakest reserve, flagged. Never a default value. */
export function referenceGap(i: { crop_row: CropRow | null; soil_rows: SoilRow[]; texture: string | null }): {
  unavailable_reason: string | null; soil_reserve_mm_per_m?: number; texture_used?: string; soil_default?: boolean; validated?: boolean;
} {
  const c = i.crop_row;
  if (!c || typeof c.kc !== "number") return { unavailable_reason: "no_crop_coefficient" };
  if (typeof c.root_depth_m !== "number") return { unavailable_reason: "no_root_depth" };
  if (typeof c.depletion_fraction !== "number") return { unavailable_reason: "no_depletion_fraction" };
  if (i.soil_rows.length === 0) return { unavailable_reason: "no_soil_reference" };
  const withReserve = i.soil_rows.filter((r) => typeof r.available_water_mm_per_m === "number");
  const match = i.texture ? i.soil_rows.find((r) => r.texture_key === i.texture) : undefined;
  if (match) {
    if (typeof match.available_water_mm_per_m !== "number") return { unavailable_reason: "no_soil_reserve" };
    return { unavailable_reason: null, soil_reserve_mm_per_m: match.available_water_mm_per_m, texture_used: match.texture_key, soil_default: false, validated: c.validated };
  }
  if (withReserve.length === 0) return { unavailable_reason: "no_soil_reserve" };
  const weakest = withReserve.reduce((a, b) => ((b.available_water_mm_per_m as number) < (a.available_water_mm_per_m as number) ? b : a));
  return { unavailable_reason: null, soil_reserve_mm_per_m: weakest.available_water_mm_per_m as number, texture_used: weakest.texture_key, soil_default: true, validated: c.validated };
}
