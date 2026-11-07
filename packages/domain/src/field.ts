import { areaHa } from "./area";
import { centroid, isInMorocco, validateRing } from "./geometry";
import type { Pt } from "./area";

export const LIMITS = {
  MIN_VERTICES: 3,
  MAX_VERTICES: 500,
  MAX_AREA_HA: 5000,
  MAX_FIELDS_PER_FARM: 500,
  MAX_NAME_LENGTH: 80,
} as const;

export const IMAGERY_MIN_AREA_HA = 0.3;

export function canCreateField(currentCount: number): { ok: true } | { ok: false; code: "field_limit_reached" } {
  return currentCount < LIMITS.MAX_FIELDS_PER_FARM ? { ok: true } : { ok: false, code: "field_limit_reached" };
}

/** Satellite imagery needs at least 0.3 ha and no greenhouse. */
export function imagerySuitable(areaHaValue: number, underGreenhouse: boolean): boolean {
  return areaHaValue >= IMAGERY_MIN_AREA_HA && !underGreenhouse;
}

export const IRRIGATION_MODES = ["rainfed", "gravity", "sprinkler", "drip", "pivot"] as const;
export type IrrigationMode = (typeof IRRIGATION_MODES)[number];

/** null/undefined means "not filled in yet" and is accepted. */
export function isIrrigationMode(value: unknown): value is IrrigationMode | null | undefined {
  return value == null || (IRRIGATION_MODES as readonly unknown[]).includes(value);
}

export type FieldInput = {
  name: string;
  ring: readonly Pt[];
  areaDeclaredHa?: number | null;
  irrigation?: IrrigationMode | null;
  greenhouse?: boolean | null;
};

export function validateField(input: FieldInput):
  | { ok: true; ring: Pt[]; areaHa: number; areaDeclaredHa: number | null; irrigation: IrrigationMode | null; greenhouse: boolean }
  | { ok: false; code: string; [k: string]: unknown } {
  const name = typeof input.name === "string" ? input.name.trim() : "";
  if (name.length < 1 || name.length > LIMITS.MAX_NAME_LENGTH) return { ok: false, code: "name_invalid" };
  const r = validateRing(input.ring);
  if (!r.ok) return r;
  if (!isInMorocco(centroid(r.ring))) return { ok: false, code: "outside_morocco" };
  const ha = areaHa(r.ring);
  if (ha > LIMITS.MAX_AREA_HA) return { ok: false, code: "area_too_large" };
  if (input.areaDeclaredHa != null && !(input.areaDeclaredHa > 0)) return { ok: false, code: "area_declared_invalid" };
  if (!isIrrigationMode(input.irrigation)) return { ok: false, code: "irrigation_invalid" };
  if (input.greenhouse != null && typeof input.greenhouse !== "boolean") return { ok: false, code: "greenhouse_invalid" };
  return {
    ok: true,
    ring: r.ring,
    areaHa: ha,
    areaDeclaredHa: input.areaDeclaredHa ?? null,
    irrigation: input.irrigation ?? null,
    greenhouse: input.greenhouse ?? false,
  };
}
