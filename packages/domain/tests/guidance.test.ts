import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { guidance } from "../src/guidance";

const v = JSON.parse(readFileSync(new URL("../vectors/f3_guidance.json", import.meta.url), "utf-8"));

describe("F3 straight-line guidance (heading and distance)", () => {
  for (const c of v.cases) {
    it(`given a target to the ${c.name} then heading and distance match`, () => {
      const g = guidance(v.from, c.to);
      const d = Math.abs(((g.bearingDeg - c.bearing + 540) % 360) - 180);
      expect(c.distance_m === 0 ? 0 : d).toBeLessThanOrEqual(v.tolerance.bearing_deg);
      expect(Math.abs(g.distanceM - c.distance_m)).toBeLessThanOrEqual(Math.max(v.tolerance.distance_abs_m, c.distance_m * v.tolerance.distance_ratio));
    });
  }
  it("given a bearing then it is always within [0, 360)", () => {
    const g = guidance(v.from, { lat: 33.569, lon: -7.601 });
    expect(g.bearingDeg).toBeGreaterThanOrEqual(0);
    expect(g.bearingDeg).toBeLessThan(360);
  });
});
