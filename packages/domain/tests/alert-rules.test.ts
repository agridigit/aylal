import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { dedupKey, evaluateDay } from "../src/alert-rules";
import { thresholdsFor } from "../src/weather-thresholds";

const v = JSON.parse(readFileSync(new URL("../vectors/f3_alert_rules.json", import.meta.url), "utf-8"));

describe("F3 alert rules", () => {
  for (const c of v.evaluations) {
    it(`given ${c.name} then the alerts match`, () => {
      const out = evaluateDay(thresholdsFor(v.thresholds, c.crop_slug, c.stage_key), c.day);
      expect(out.map((a: { type: string }) => a.type).sort()).toEqual(c.expected.map((e: { type: string }) => e.type).sort());
      for (const e of c.expected) {
        const got = out.find((a: { type: string }) => a.type === e.type);
        if (e.severity) expect(got.severity).toBe(e.severity);
        if (e.advice_key) expect(got.adviceKey).toBe(e.advice_key);
      }
    });
  }
  it("given no thresholds for the pair then no alert is produced", () => {
    expect(evaluateDay(null, { date: "2026-12-05", tmin: -9, tmax: 50, rain_mm: 99, wind_kmh: 99, humidity_pct: 1 })).toEqual([]);
  });
  it("given the same inputs then the dedup key is stable and 64 hex characters", () => {
    const a = dedupKey({ farmId: v.dedup.base.farm_id, parcelId: v.dedup.base.parcel_id, cropSlug: v.dedup.base.crop_slug, type: v.dedup.base.type, forecastDay: v.dedup.base.forecast_day });
    expect(a).toMatch(/^[0-9a-f]{64}$/);
    expect(a).toBe(dedupKey({ farmId: v.dedup.base.farm_id, parcelId: v.dedup.base.parcel_id, cropSlug: v.dedup.base.crop_slug, type: v.dedup.base.type, forecastDay: v.dedup.base.forecast_day }));
  });
  it("given any one component changing then the dedup key changes", () => {
    const b = v.dedup.base;
    const key = (o: Record<string, string>) => dedupKey({ farmId: o.farm_id, parcelId: o.parcel_id, cropSlug: o.crop_slug, type: o.type, forecastDay: o.forecast_day });
    const keys = new Set([key(b), ...v.dedup.variants.map((x: object) => key({ ...b, ...x }))]);
    expect(keys.size).toBe(v.dedup.variants.length + 1);
  });
});
