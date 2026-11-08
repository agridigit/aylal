import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { isAnomalousZone, isResolved } from "../src/anomaly";

const v = JSON.parse(readFileSync(new URL("../vectors/f3_anomaly.json", import.meta.url), "utf-8"));

describe("F3 vigor anomaly (thresholds from fixtures)", () => {
  for (const z of v.zones) {
    it(`given a drop of ${z.drop_score} over ${z.pixels} pixels then anomalous is ${z.anomalous}`, () => {
      expect(isAnomalousZone({ dropScore: z.drop_score, pixels: z.pixels }, { anomalyDrop: v.params.anomaly_drop, anomalyMinPixels: v.params.anomaly_min_pixels })).toBe(z.anomalous);
    });
  }
  for (const r of v.resolution) {
    it(`given recent vigor ${JSON.stringify(r.recent_vigor)} then resolved is ${r.resolved}`, () => {
      expect(isResolved(r.recent_vigor, r.threshold)).toBe(r.resolved);
    });
  }
});
