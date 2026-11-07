import { describe, expect, it } from "vitest";
import { IRRIGATION_MODES, LIMITS, canCreateField, imagerySuitable, isIrrigationMode, validateField } from "../src/field";
import { square } from "./_f2";

const ring = square(-7.6, 33.57, 0.001);

describe("field limits", () => {
  it("given the limits then they match the spec", () => {
    expect(LIMITS).toMatchObject({ MIN_VERTICES: 3, MAX_VERTICES: 500, MAX_AREA_HA: 5000, MAX_FIELDS_PER_FARM: 500, MAX_NAME_LENGTH: 80 });
  });
  it("given 499 fields when creating one more then it is allowed, at 500 it is field_limit_reached", () => {
    expect(canCreateField(499)).toEqual({ ok: true });
    expect(canCreateField(500)).toEqual({ ok: false, code: "field_limit_reached" });
  });
});

describe("validateField", () => {
  it("given a valid name and ring when validating then ok with a computed area", () => {
    const r: any = validateField({ name: "Haouz", ring });
    expect(r.ok).toBe(true);
    expect(r.areaHa).toBeCloseTo(1.03, 1);
  });
  it("given an empty or blank name when validating then name_invalid", () => {
    expect((validateField({ name: "  ", ring }) as any).code).toBe("name_invalid");
  });
  it("given a name of 80 characters then ok, of 81 then name_invalid", () => {
    expect(validateField({ name: "a".repeat(80), ring }).ok).toBe(true);
    expect((validateField({ name: "a".repeat(81), ring }) as any).code).toBe("name_invalid");
  });
  it("given a field centroid outside Morocco when validating then outside_morocco", () => {
    expect((validateField({ name: "Paris", ring: square(2.35, 48.85, 0.001) }) as any).code).toBe("outside_morocco");
  });
  it("given an area above 5000 ha when validating then area_too_large", () => {
    expect((validateField({ name: "Huge", ring: square(-7.6, 33.0, 0.5) }) as any).code).toBe("area_too_large");
  });
  it("given a bow tie when validating then the ring error code is propagated", () => {
    const bow: [number, number][] = [[-7.6, 33.57], [-7.598, 33.572], [-7.598, 33.57], [-7.6, 33.572], [-7.6, 33.57]];
    expect((validateField({ name: "Bow", ring: bow }) as any).code).toBe("self_intersection");
  });
  it("given a declared area not above zero when validating then area_declared_invalid", () => {
    expect((validateField({ name: "X", ring, areaDeclaredHa: 0 }) as any).code).toBe("area_declared_invalid");
  });
});

describe("imagerySuitable", () => {
  it("given area and greenhouse when checking then area >= 0.3 and not under greenhouse", () => {
    expect(imagerySuitable(0.3, false)).toBe(true);
    expect(imagerySuitable(0.29, false)).toBe(false);
    expect(imagerySuitable(5, true)).toBe(false);
  });
});

describe("irrigation and greenhouse (R3-A1, R3-A2)", () => {
  it("given the five irrigation modes then they are exactly rainfed, gravity, sprinkler, drip and pivot", () => {
    expect([...IRRIGATION_MODES]).toEqual(["rainfed", "gravity", "sprinkler", "drip", "pivot"]);
  });
  it("given each mode or no mode when checking then it is accepted, an unknown mode is not", () => {
    for (const m of IRRIGATION_MODES) expect(isIrrigationMode(m)).toBe(true);
    expect(isIrrigationMode(null)).toBe(true); // not filled in yet
    expect(isIrrigationMode("flood")).toBe(false);
  });
  it("given an irrigation mode and a greenhouse flag when validating a field then both are returned", () => {
    const r = validateField({ name: "A", ring, irrigation: "drip", greenhouse: true });
    expect(r).toMatchObject({ ok: true, irrigation: "drip", greenhouse: true });
  });
  it("given no irrigation and no greenhouse when validating a field then irrigation is null and greenhouse false", () => {
    expect(validateField({ name: "A", ring })).toMatchObject({ ok: true, irrigation: null, greenhouse: false });
  });
  it("given an unknown irrigation mode or a non boolean greenhouse when validating then irrigation_invalid or greenhouse_invalid", () => {
    expect(validateField({ name: "A", ring, irrigation: "flood" as never })).toMatchObject({ ok: false, code: "irrigation_invalid" });
    expect(validateField({ name: "A", ring, greenhouse: "yes" as never })).toMatchObject({ ok: false, code: "greenhouse_invalid" });
  });
  it("given the 0.3 ha boundary and a greenhouse when checking imagery then a greenhouse always makes it unsuitable", () => {
    expect(imagerySuitable(0.3, true)).toBe(false);
    expect(imagerySuitable(0.2999, false)).toBe(false);
  });
});

describe("declared area kept apart from the calculated one (R1-A5)", () => {
  it("given a declared area different from the calculated one when validating then both are returned unchanged", () => {
    const r = validateField({ name: "A", ring, areaDeclaredHa: 7.5 });
    expect(r).toMatchObject({ ok: true, areaDeclaredHa: 7.5 });
    expect((r as { areaHa: number }).areaHa).not.toBe(7.5);
  });
  it("given no declared area when validating then areaDeclaredHa is null", () => {
    expect(validateField({ name: "A", ring })).toMatchObject({ ok: true, areaDeclaredHa: null });
  });
});
