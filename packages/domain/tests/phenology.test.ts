import { describe, expect, it } from "vitest";
import { displayStage, estimateStage } from "../src/phenology";

const wheat = {
  cycle: "annual",
  stages: [
    { key: "emergence", gdd_from: 0, label_key: "stage.emergence" },
    { key: "tillering", gdd_from: 100, label_key: "stage.tillering" },
    { key: "heading", gdd_from: 400, label_key: "stage.heading" },
  ],
};

describe("estimateStage", () => {
  it("given no GDD when estimating then elapsed days are used and the result is labelled approximate", () => {
    const r = estimateStage(wheat, { sowing_date: "2026-01-01" }, "2026-01-21");
    expect(r).toEqual({ stage: "emergence", approximate: true });
    expect(estimateStage(wheat, { sowing_date: "2026-01-01" }, "2026-05-01")).toEqual({ stage: "tillering", approximate: true });
  });
  it("given a GDD value when estimating then it drives the stage and is not approximate", () => {
    expect(estimateStage(wheat, { sowing_date: "2026-01-01" }, "2026-02-01", 450)).toEqual({ stage: "heading", approximate: false });
  });
  it("given a custom crop without stages when estimating then there is no stage", () => {
    expect(estimateStage({ cycle: "annual", stages: [] }, { sowing_date: "2026-01-01" }, "2026-05-01")).toEqual({ stage: null, approximate: false });
  });
  it("given a stage_corrected when displaying then it wins over the estimate", () => {
    expect(displayStage({ stage_estimated: "tillering", stage_corrected: "heading" })).toBe("heading");
    expect(displayStage({ stage_estimated: "tillering", stage_corrected: null })).toBe("tillering");
  });
});
