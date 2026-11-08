const DAY = 86_400_000;

/** R5-A4: age of an analysis in whole days; a date after today is refused, never negative. */
export function analysisAgeDays(i: { analysed_on: string; today: string }): { age_days: number | null; error?: string } {
  const age = Math.round((Date.parse(i.today) - Date.parse(i.analysed_on)) / DAY);
  return age < 0 ? { age_days: null, error: "in_the_future" } : { age_days: age };
}

/** Assumptions an analysis adds to the advice: salinity, source, age and the leaching fraction (or why there is none). */
export function analysisAssumptions(i: {
  ec_ds_m: number; water_source: string; analysed_on: string; today: string; leaching_fraction: number | null; unavailable_reason: string | null;
}): any[] {
  const out: { key: string; value: number | string }[] = [{ key: "ece_ds_m", value: i.ec_ds_m }];
  if (i.water_source) out.push({ key: "water_source", value: i.water_source });
  const age = analysisAgeDays(i).age_days;
  if (age !== null) out.push({ key: "analysis_age_days", value: age });
  if (i.leaching_fraction !== null) out.push({ key: "leaching_fraction", value: i.leaching_fraction });
  else if (i.unavailable_reason) out.push({ key: "leaching_unavailable_reason", value: i.unavailable_reason });
  return out;
}

/** Old only against a referential limit; without a limit never judged old. */
export function isOldAnalysis(i: { age_days: number; max_age_days: number | null }): { old: boolean } {
  return { old: i.max_age_days !== null && i.age_days > i.max_age_days };
}
