/** value * to = from: `up` multiplies by 1000, `down` divides by 1000 (exact for the vectors). */
const STEP: Record<string, Record<string, "up" | "down">> = {
  "L/ha": { "mL/ha": "up" },
  "mL/ha": { "L/ha": "down" },
  "kg/ha": { "g/ha": "up" },
  "g/ha": { "kg/ha": "down" },
};

export const DOSE_UNITS = ["L/ha", "mL/ha", "kg/ha", "g/ha"] as const;

/** Convert a dose between compatible units; null when the units are not convertible. */
export function convertDose(value: number, from: string, to: string): number | null {
  if (from === to) return value;
  const step = STEP[from]?.[to];
  if (step === undefined) return null;
  return step === "up" ? value * 1000 : value / 1000;
}
