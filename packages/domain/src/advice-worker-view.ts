/** Worker-safe view of an advice (decisions point 19): deny-by-default whitelists, no mutation. */
export const WORKER_ASSUMPTION_KEYS = ["et0", "kc", "effective_rain", "efficiency", "application_rate", "rain_source"] as const;

export const WORKER_ADVICE_KEYS = [
  "parcel_id", "for_date", "kind", "total_minutes", "sectors", "net_need_mm", "stress_level", "confidence",
  "assumptions", "unavailable_reason", "computed_at", "is_last_known", "ready_before_7",
] as const;

type Assumption = { key: string; value: unknown; source: string };

export function workerAssumptions(i: { assumptions: Assumption[] }): { assumptions: Assumption[] } {
  const allowed = new Set<string>(WORKER_ASSUMPTION_KEYS);
  return { assumptions: structuredClone(i.assumptions.filter((a) => allowed.has(a.key))) };
}

export function adviceView(i: { role: string; advice: Record<string, unknown> }): Record<string, unknown> {
  const advice = structuredClone(i.advice);
  if (i.role === "owner" || i.role === "manager") return advice;
  const out: Record<string, unknown> = {};
  for (const k of WORKER_ADVICE_KEYS) if (k in advice) out[k] = advice[k];
  if (Array.isArray(out.assumptions)) out.assumptions = workerAssumptions({ assumptions: out.assumptions as Assumption[] }).assumptions;
  return out;
}
