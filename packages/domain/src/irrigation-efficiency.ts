/** Default efficiencies (CPS section 9): drip 90 %, sprinkler 75 %, gravity 60 %; pivot treated as sprinkler. */
const DEFAULTS: Record<string, number> = { drip: 0.9, sprinkler: 0.75, pivot: 0.75, gravity: 0.6 };

export function resolveEfficiency(i: { kind: string; efficiency: number | null }): { efficiency: number | null; is_default: boolean } {
  if (i.efficiency !== null && i.efficiency !== undefined) return { efficiency: i.efficiency, is_default: false };
  return { efficiency: DEFAULTS[i.kind] ?? null, is_default: true };
}
