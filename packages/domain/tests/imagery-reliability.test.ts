import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { imageryReliability } from "../src/imagery-reliability";

const v: { area_ha: number; greenhouse: boolean; reliability: string }[] = JSON.parse(readFileSync(new URL("../vectors/f3_reliability.json", import.meta.url), "utf-8"));

describe("F3 imagery reliability (FR-009)", () => {
  for (const c of v) {
    it(`given ${c.area_ha} ha greenhouse=${c.greenhouse} then reliability is ${c.reliability}`, () => {
      expect(imageryReliability({ areaHa: c.area_ha, greenhouse: c.greenhouse }, 0.3)).toBe(c.reliability);
    });
  }
});
