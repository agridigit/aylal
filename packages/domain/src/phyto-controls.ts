import { convertDose } from "./units";

/** Warning codes, in the stable order they are reported. Warnings never block a save. */
export const WARNING_CODES = [
  "not_authorized_for_crop",
  "dose_above_max",
  "max_applications_reached",
  "dar_unknown",
  "free_product_unchecked",
] as const;
export type WarningCode = (typeof WARNING_CODES)[number];

export interface ProductUse {
  crop_slug: string;
  max_dose: number | null;
  dose_unit: string | null;
  dar_days: number | null;
  max_applications: number | null;
}

export interface PhytoInput {
  product_id?: string | null;
  free_product_name?: string | null;
  uses: readonly ProductUse[];
  crop_slug: string | null;
  dose?: number | null;
  dose_unit?: string | null;
  applications_so_far: number;
}

/** Controls of a phyto treatment on one parcel. Mirror: services/api/app/domain/phyto_controls.py. */
export function phytoWarnings(input: PhytoInput): WarningCode[] {
  if (!input.product_id) return input.free_product_name ? ["free_product_unchecked"] : [];
  const use = input.crop_slug ? input.uses.find((u) => u.crop_slug === input.crop_slug) : undefined;
  if (!use) return ["not_authorized_for_crop"];
  const out: WarningCode[] = [];
  if (input.dose != null && input.dose_unit && use.max_dose != null && use.dose_unit) {
    const converted = convertDose(input.dose, input.dose_unit, use.dose_unit);
    if (converted !== null && converted > use.max_dose + 1e-9) out.push("dose_above_max");
  }
  if (use.max_applications != null && input.applications_so_far >= use.max_applications) out.push("max_applications_reached");
  if (use.dar_days == null) out.push("dar_unknown");
  return out;
}

export interface ParcelContext {
  id: string;
  crop_slug: string | null;
  applications_so_far: number;
}

/** The same controls applied parcel by parcel (each parcel has its own crop and count). */
export function phytoWarningsByParcel(
  base: Omit<PhytoInput, "crop_slug" | "applications_so_far">,
  parcels: readonly ParcelContext[],
): Record<string, WarningCode[]> {
  const out: Record<string, WarningCode[]> = {};
  for (const p of parcels) {
    out[p.id] = phytoWarnings({ ...base, crop_slug: p.crop_slug, applications_so_far: p.applications_so_far });
  }
  return out;
}
