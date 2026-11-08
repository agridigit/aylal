type Plan = { for_date: string; kind: string; confidence: string };

/** R2-A6: today's valid plan; else the latest older valid plan (dated, confidence lowered to low); else the latest unavailable one; else nothing. */
export function selectServedPlan(i: { plans: Plan[]; today: string }): { served: Plan | null; is_last_known: boolean; confidence: string } {
  const past = i.plans.filter((p) => p.for_date <= i.today);
  const latest = (xs: Plan[]) => xs.reduce<Plan | null>((a, p) => (a === null || p.for_date > a.for_date ? p : a), null);
  const valid = latest(past.filter((p) => p.kind !== "unavailable"));
  if (valid) {
    const last = valid.for_date < i.today;
    return { served: valid, is_last_known: last, confidence: last ? "low" : valid.confidence };
  }
  const un = latest(past);
  return un ? { served: un, is_last_known: false, confidence: "low" } : { served: null, is_last_known: false, confidence: "low" };
}
