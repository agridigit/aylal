import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { allocate } from "../src/allocation";

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
