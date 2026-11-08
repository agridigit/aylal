import { describe, expect, it } from "vitest";
import * as mod from "../src/advice-worker-view";
import { rawVectors, runVectors } from "./_f4";

describe("F4 worker view of an advice (shared vectors f4_worker_view.json, decisions point 19)", () => {
  runVectors(mod as Record<string, unknown>, "f4_worker_view.json");

  it("given the whitelist then it is exactly the six documented keys", () => {
    expect([...(mod as any).WORKER_ASSUMPTION_KEYS].sort()).toEqual([...rawVectors("f4_worker_view.json").whitelist].sort());
  });
  it("given hypotheses with salinity, water source, analysis age, soil and reserve when building the worker view then none of their keys survives at any depth", () => {
    const { cases } = rawVectors("f4_worker_view.json");
    const c = cases.find((x: any) => x.fn === "advice_view" && x.input.role === "worker");
    const out = JSON.stringify((mod as any).adviceView(structuredClone(c.input)));
    for (const k of ["ece", "ecw", "salin", "water_source", "analysis_age", "soil", "taw", "raw_mm", "moisture", "leaching", "cost", "x_future"]) {
      expect(out.includes(`"${k}`), k).toBe(false);
    }
  });
  it("given an input advice when building the worker view then the input is not mutated", () => {
    const { cases } = rawVectors("f4_worker_view.json");
    const c = cases.find((x: any) => x.fn === "advice_view" && x.input.role === "worker");
    const before = JSON.stringify(c.input);
    (mod as any).adviceView(c.input);
    expect(JSON.stringify(c.input)).toBe(before);
  });
});
