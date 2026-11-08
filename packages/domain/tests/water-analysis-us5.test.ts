/** T074 (US5) - water analysis and leaching. New file (the shared vector file f4_leaching.json is not extended): the age of the analysis
 *  and the assumptions it adds to the advice (R5-A4), the leaching rule on top of the existing FAO-29 vectors (R5-A2, R5-A3) and the
 *  missing salinity reference (nothing invented, a reason). `water-analysis` does not exist yet: imported inside each test. */
import { describe, expect, it } from "vitest";
import { computeAdvice } from "../src/irrigation-advice";
import { leachingFraction } from "../src/leaching";

const load = async () => await import("../src/water-analysis");
const CROP = { ece_threshold_ds_m: 2, ece_max_ds_m: 8, leaching_max: 0.15 };
const SYSTEM = { efficiency: 0.9, rate_mm_h: 4, sectors_count: 1 };
const advise = (lr: number | null) => computeAdvice({ irrigated: true, greenhouse: false, has_system: true, system: SYSTEM, depletion_mm: 30, raw_mm: 25, rain_mm_today: 0, leaching_fraction: lr, stress_watch_ratio: 0.5 });

describe("F4 US5 leaching on the shared rule (R5-A2, R5-A3)", () => {
  it("given a salinity above the threshold when computing then LR = ECw / (5 ECe_max - ECw) and the duration is longer (R5-A2)", () => {
    const lr = leachingFraction({ ecw_ds_m: 3.1, ...CROP }).leaching_fraction as number;
    expect(lr).toBeCloseTo(3.1 / (40 - 3.1), 4);
    expect(advise(lr).total_minutes as number).toBeGreaterThan(advise(0).total_minutes as number);
  });

  it("given a salinity at or below the threshold when computing then no leaching is added and the duration is unchanged (R5-A3)", () => {
    expect(leachingFraction({ ecw_ds_m: 2, ...CROP }).leaching_fraction).toBe(0);
    expect(advise(0).total_minutes).toBe(advise(null).total_minutes);
  });

  it("given a missing salinity reference when computing then there is no leaching and the reason is given", () => {
    const out = leachingFraction({ ecw_ds_m: 3.1, ece_threshold_ds_m: 2, ece_max_ds_m: null, leaching_max: 0.15 });
    expect(out.leaching_fraction).toBeNull();
    expect(out.unavailable_reason).toBe("no_salinity_reference");
  });
});

describe("F4 US5 analysis age and assumptions (R5-A4)", () => {
  it("given an analysis of 2026-05-01 and today 2026-06-04 when asking its age then it is 34 days", async () => {
    const { analysisAgeDays } = await load();
    expect(analysisAgeDays({ analysed_on: "2026-05-01", today: "2026-06-04" })).toEqual({ age_days: 34 });
  });

  it("given an analysis dated in the future when asking its age then it is refused, not negative", async () => {
    const { analysisAgeDays } = await load();
    expect(analysisAgeDays({ analysed_on: "2026-06-05", today: "2026-06-04" })).toEqual({ age_days: null, error: "in_the_future" });
  });

  it("given an analysis and a leaching fraction when listing the assumptions then the salinity, the source, the age and the fraction are stated", async () => {
    const { analysisAssumptions } = await load();
    const out = analysisAssumptions({ ec_ds_m: 3.1, water_source: "well-42", analysed_on: "2026-05-01", today: "2026-06-04", leaching_fraction: 0.084, unavailable_reason: null });
    expect(out.map((a: { key: string }) => a.key)).toEqual(["ece_ds_m", "water_source", "analysis_age_days", "leaching_fraction"]);
    expect(out.find((a: { key: string }) => a.key === "analysis_age_days").value).toBe(34);
  });

  it("given a missing salinity reference when listing the assumptions then no fraction is stated and the reason is", async () => {
    const { analysisAssumptions } = await load();
    const out = analysisAssumptions({ ec_ds_m: 3.1, water_source: "", analysed_on: "2026-05-01", today: "2026-06-04", leaching_fraction: null, unavailable_reason: "no_salinity_reference" });
    expect(out.map((a: { key: string }) => a.key)).not.toContain("leaching_fraction");
    expect(out.find((a: { key: string }) => a.key === "leaching_unavailable_reason").value).toBe("no_salinity_reference");
  });

  it("given an analysis older than the referential limit when assessing then it is old, and without a limit it is never judged old", async () => {
    const { isOldAnalysis } = await load();
    expect(isOldAnalysis({ age_days: 400, max_age_days: 365 })).toEqual({ old: true });
    expect(isOldAnalysis({ age_days: 400, max_age_days: null })).toEqual({ old: false });
  });
});
