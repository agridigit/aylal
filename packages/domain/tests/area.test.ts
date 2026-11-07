import { describe, expect, it } from "vitest";
import { areaHa, displayAreaHa } from "../src/area";
import { vectors } from "./_f2";

describe("areaHa shared vectors (spherical excess, 0.5 percent tolerance)", () => {
  for (const v of vectors("f2_area.json")) {
    it(`given ${v.name} when computing the area then it is within 0.5 percent of ${v.expectedHa} ha`, () => {
      expect(Math.abs(areaHa(v.ring) - v.expectedHa) / v.expectedHa).toBeLessThan(0.005);
    });
  }
  it("given an area when displaying then it is rounded to 2 decimals", () => {
    expect(displayAreaHa(1.03024)).toBe(1.03);
    expect(displayAreaHa(1.035)).toBe(1.04);
  });
});
