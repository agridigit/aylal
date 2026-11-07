import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { allocate, allocationBreakdown } from "../src/allocation";

const vectors: { name: string; total: number; areas: number[]; expected: number[] }[] = JSON.parse(
  readFileSync(new URL("../vectors/f6_allocation.json", import.meta.url), "utf-8"),
);

describe("F6 allocation of a quantity across parcels by area", () => {
  for (const v of vectors) {
    it(`given ${v.name} when allocating then shares match and sum to the total`, () => {
      const out = allocate(v.total, v.areas);
      expect(out).toEqual(v.expected);
      expect(Math.round(out.reduce((a, b) => a + b, 0) * 1000) / 1000).toBe(v.total);
    });
  }
  it("given no parcel when allocating then it throws", () => {
    expect(() => allocate(1, [])).toThrow();
  });
});

describe("F6 allocation display (R1-A3)", () => {
  it("given a total across parcels when building the breakdown then each line carries id, share and area percent", () => {
    const lines = allocationBreakdown(10, [
      { id: "a", area_ha: 1 },
      { id: "b", area_ha: 3 },
    ]);
    expect(lines).toEqual([
      { id: "a", share: 2.5, percent: 25 },
      { id: "b", share: 7.5, percent: 75 },
    ]);
  });
  it("given rounding when building the breakdown then the shares still add up to the total", () => {
    const lines = allocationBreakdown(10, [{ id: "a", area_ha: 1 }, { id: "b", area_ha: 1 }, { id: "c", area_ha: 1 }]);
    expect(Math.round(lines.reduce((s, l) => s + l.share, 0) * 1000) / 1000).toBe(10);
  });
  it("given parcels without area when building the breakdown then the split is equal", () => {
    expect(allocationBreakdown(4, [{ id: "a", area_ha: null }, { id: "b", area_ha: null }]).map((l) => l.share)).toEqual([2, 2]);
  });
});
