import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { phytoWarnings, phytoWarningsByParcel } from "../src/phyto-controls";

const v = JSON.parse(readFileSync(new URL("../vectors/f6_phyto_controls.json", import.meta.url), "utf-8"));

describe("F6 phyto controls (R2-A3, R2-A4, R2-A5, R2-A7): warnings only, never blocking", () => {
  for (const c of v.cases) {
    it(`given ${c.name} when checking then the warnings match the vector`, () => {
      expect(phytoWarnings(c.input)).toEqual(c.expected);
    });
  }
  for (const c of v.by_parcel) {
    it(`given ${c.name} when checking then each parcel gets its own warnings`, () => {
      expect(phytoWarningsByParcel(c.base, c.parcels)).toEqual(c.expected);
    });
  }
  it("given any input when checking then the result is a list of codes and never throws", () => {
    for (const c of v.cases) expect(Array.isArray(phytoWarnings(c.input))).toBe(true);
  });
});
