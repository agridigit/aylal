import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { thresholdsFor } from "../src/weather-thresholds";

const v = JSON.parse(readFileSync(new URL("../vectors/f3_alert_rules.json", import.meta.url), "utf-8"));

describe("F3 thresholds per crop and stage (fixtures only)", () => {
  for (const l of v.lookups) {
    it(`given ${l.crop_slug}/${l.stage_key} when looking up then found is ${l.found}`, () => {
      const t = thresholdsFor(v.thresholds, l.crop_slug, l.stage_key);
      expect(t !== null).toBe(l.found);
    });
  }
  it("given an unknown pair then null is returned and nothing is invented", () => {
    expect(thresholdsFor(v.thresholds, "fixture_unknown", "fixture_unknown")).toBeNull();
  });
});
