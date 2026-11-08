import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { parcelStatus, sortParcels } from "../src/parcel-status";

const v = JSON.parse(readFileSync(new URL("../vectors/f3_parcel_status.json", import.meta.url), "utf-8"));

describe("F3 parcel status (FR-012, FR-014)", () => {
  for (const c of v.cases) {
    it(`given ${c.name} then colour, reason and sources match`, () => {
      const s = parcelStatus(c.signals, c.now, c.doubts);
      expect(s.color).toBe(c.expected.color);
      expect(s.reasonKey).toBe(c.expected.reason_key);
      expect(s.items.map((i: { source: string }) => i.source)).toEqual(c.expected.item_sources);
    });
  }
  it("given parcels of all colours then red come first, then orange, then green, ties by contributors then name", () => {
    const out = sortParcels(v.sorting.parcels.map((p: { id: string; color: string; contributors: number; name: string }) => p));
    expect(out.map((p: { id: string }) => p.id)).toEqual(v.sorting.expected);
  });
});
