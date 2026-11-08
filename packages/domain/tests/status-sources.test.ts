import { describe, expect, it } from "vitest";
import { collectSignals } from "../src/status-sources";

const sig = (source: string) => ({ source, severity: "watch", reason_key: `status.${source}`, observed_at: "2026-12-05T08:00:00Z", ttl_s: 3600 });

describe("F3 status source registry (FR-013)", () => {
  it("given unregistered F4 and F5 sources then they are ignored without error", () => {
    const out = collectSignals({ weather_alert: () => [sig("weather_alert")], irrigation_need: undefined, health_risk: undefined });
    expect(out.map((s) => s.source)).toEqual(["weather_alert"]);
  });
  it("given a source that reports unavailable then it yields no signal and no error", () => {
    expect(collectSignals({ weather_alert: () => "unavailable" })).toEqual([]);
  });
  it("given a source that throws then it is ignored and the others still count", () => {
    const out = collectSignals({ vigor_anomaly: () => { throw new Error("boom"); }, overdue_operations: () => [sig("overdue_operations")] });
    expect(out.map((s) => s.source)).toEqual(["overdue_operations"]);
  });
});
