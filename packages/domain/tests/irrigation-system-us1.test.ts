/** T047 (US1) - describing an irrigation system. New file: the existing shared-vector files are not extended (they would change
 *  the existing tests). The validator module does not exist yet: it is imported inside each test so that the failure is the
 *  missing feature, not a collection error. */
import { describe, expect, it } from "vitest";
import { applicationRate } from "../src/application-rate";
import { resolveEfficiency } from "../src/irrigation-efficiency";

const load = async () => await import("../src/irrigation-system-validation");
const PUMP = { kind: "drip", sectors_count: 2, pump_flow_m3h: 10 };

describe("F4 US1 system validation (R1-A2, R1-A5)", () => {
  it("given a system described by the pump flow when validating then it is accepted without emitter flow or spacings (R1-A2)", async () => {
    const { validateIrrigationSystem } = await load();
    expect(validateIrrigationSystem(PUMP)).toEqual({ valid: true, errors: [] });
  });

  it("given a drip system with emitters and spacings when validating then it is accepted (R1-A1)", async () => {
    const { validateIrrigationSystem } = await load();
    expect(validateIrrigationSystem({ kind: "drip", sectors_count: 2, emitter_flow_lph: 4, emitter_spacing_m: 0.5, row_spacing_m: 2 }).valid).toBe(true);
  });

  it.each([
    ["emitter_flow_lph", { kind: "drip", sectors_count: 2, emitter_flow_lph: 0, emitter_spacing_m: 0.5, row_spacing_m: 2 }],
    ["emitter_flow_lph", { kind: "drip", sectors_count: 2, emitter_flow_lph: -3, emitter_spacing_m: 0.5, row_spacing_m: 2 }],
    ["emitter_spacing_m", { kind: "drip", sectors_count: 2, emitter_flow_lph: 4, emitter_spacing_m: 0, row_spacing_m: 2 }],
    ["row_spacing_m", { kind: "drip", sectors_count: 2, emitter_flow_lph: 4, emitter_spacing_m: 0.5, row_spacing_m: 0 }],
    ["pump_flow_m3h", { ...PUMP, pump_flow_m3h: 0 }],
    ["sectors_count", { ...PUMP, sectors_count: 0 }],
    ["efficiency", { ...PUMP, efficiency: 0 }],
  ])("given an incoherent value in %s when validating then the field is named with an i18n key (R1-A5)", async (field, input) => {
    const { validateIrrigationSystem } = await load();
    const out = validateIrrigationSystem(input);
    expect(out.valid).toBe(false);
    expect(out.errors[0].field).toBe(field);
    expect(out.errors[0].code).toMatch(/^[a-z_]+$/);
    expect(out.errors[0].i18n_key).toMatch(/^irrigation\./);
  });

  it("given a system with no flow at all when validating then it is refused on the flow, never accepted with an invented rate", async () => {
    const { validateIrrigationSystem } = await load();
    const out = validateIrrigationSystem({ kind: "sprinkler", sectors_count: 1 });
    expect(out.valid).toBe(false);
    expect(out.errors.map((e: { code: string }) => e.code)).toContain("flow_required");
  });
});

describe("F4 US1 defaults and rates already shared (R1-A3, application rate per m2)", () => {
  it.each([["drip", 0.9], ["sprinkler", 0.75], ["pivot", 0.75], ["gravity", 0.6]])("given %s without efficiency then the default %s is visible", (kind, eff) => {
    expect(resolveEfficiency({ kind, efficiency: null })).toEqual({ efficiency: eff, is_default: true });
  });

  it("given emitters 4 L/h over 0.5 m x 2 m when computing the rate then it is 4 mm/h", () => {
    expect(applicationRate({ kind: "drip", emitter_flow_lph: 4, emitter_spacing_m: 0.5, row_spacing_m: 2, pump_flow_m3h: null, sectors_count: 1, area_m2: null } as never).rate_mm_h).toBeCloseTo(4, 2);
  });
});
