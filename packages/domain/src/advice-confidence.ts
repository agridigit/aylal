export interface ConfidenceInput {
  validated: boolean;
  et0_method: string | null;
  rain_source: string | null;
  soil_default: boolean;
  efficiency_is_default: boolean;
  analysis_old: boolean;
  initial_state_assumed: boolean;
  stale: boolean;
}

/** Product rule: stale -> low; otherwise 0 factors high, 1-2 medium, 3+ low. */
export function adviceConfidence(i: ConfidenceInput): { confidence: "high" | "medium" | "low"; factors: string[] } {
  const f: string[] = [];
  if (i.stale) f.push("stale_data");
  if (!i.validated) f.push("not_validated");
  if (i.et0_method === "hargreaves") f.push("et0_estimated");
  if (i.rain_source !== null && i.rain_source !== "observed" && i.rain_source !== "ignored_greenhouse") f.push("rain_not_observed");
  if (i.soil_default) f.push("soil_default");
  if (i.efficiency_is_default) f.push("efficiency_default");
  if (i.analysis_old) f.push("analysis_old");
  if (i.initial_state_assumed) f.push("initial_state_assumed");
  const confidence = i.stale || f.length >= 3 ? "low" : f.length >= 1 ? "medium" : "high";
  return { confidence, factors: f };
}
