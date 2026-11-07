export const REFERENCE_CROP_SLUGS = [
  "olive", "citrus", "durum-wheat", "soft-wheat", "barley", "tomato", "potato", "onion",
  "berries", "avocado", "date-palm", "almond", "grape", "sugar-beet", "alfalfa", "silage-maize",
] as const;

export const CYCLES = ["perennial", "annual"] as const;
export type Cycle = (typeof CYCLES)[number];

export type CustomCropInput = { name_fr?: string; name_ar?: string; name_ary?: string; cycle: string };

/** A custom crop carries no agronomic coefficients: advice stays disabled for it. */
export function validateCustomCrop(input: CustomCropInput):
  | { ok: true; crop: { name_fr: string; name_ar?: string; name_ary?: string; cycle: Cycle; has_agronomy: false; validated: false; stages: [] } }
  | { ok: false; code: "name_invalid" | "cycle_invalid" } {
  const name = typeof input.name_fr === "string" ? input.name_fr.trim() : "";
  if (name.length < 1 || name.length > 80) return { ok: false, code: "name_invalid" };
  if (!(CYCLES as readonly string[]).includes(input.cycle)) return { ok: false, code: "cycle_invalid" };
  const crop: any = { name_fr: name, cycle: input.cycle, has_agronomy: false, validated: false, stages: [] };
  if (input.name_ar) crop.name_ar = input.name_ar.trim();
  if (input.name_ary) crop.name_ary = input.name_ary.trim();
  return { ok: true, crop };
}
