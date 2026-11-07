import { createMetric, parseMeasure, THRESHOLDS } from "../metrics";

const base = { device: "android-2gb-ref", date: "2026-11-07", build: "dev-123" };

describe("measure output (FR-028, data-model)", () => {
  it("Given a startup of 2500 ms, When creating the metric, Then it has all fields and verdict met", () => {
    const m = createMetric({ metric: "startup_ms", value: 2500, unit: "ms", ...base });
    expect(Object.keys(m).sort()).toEqual(["build", "date", "device", "metric", "threshold", "unit", "value", "verdict"]);
    expect(m.threshold).toBe(3000);
    expect(m.verdict).toBe("met");
  });

  it("Given the thresholds of CPS section 15, When reading them, Then they match", () => {
    expect(THRESHOLDS).toMatchObject({ startup_ms: 3000, map_open_ms: 2000, fps: 60, apk_size_mb: 40, daily_traffic_mb: 5 });
  });

  it("Given values over the limit, When creating the metrics, Then the verdict is not_met", () => {
    expect(createMetric({ metric: "startup_ms", value: 3001, unit: "ms", ...base }).verdict).toBe("not_met");
    expect(createMetric({ metric: "map_open_ms", value: 2001, unit: "ms", ...base }).verdict).toBe("not_met");
    expect(createMetric({ metric: "daily_traffic_mb", value: 5.1, unit: "MB", ...base }).verdict).toBe("not_met");
  });

  it("Given frames per second, When below 60, Then not_met, and at 60 met", () => {
    expect(createMetric({ metric: "fps", value: 59, unit: "fps", ...base }).verdict).toBe("not_met");
    expect(createMetric({ metric: "fps", value: 60, unit: "fps", ...base }).verdict).toBe("met");
  });

  it("Given a JSON with a missing field or bad verdict, When parsing, Then it is rejected", () => {
    const ok = createMetric({ metric: "fps", value: 60, unit: "fps", ...base });
    expect(parseMeasure(JSON.stringify(ok))).toEqual(ok);
    const { device, ...missing } = ok;
    expect(() => parseMeasure(JSON.stringify(missing))).toThrow(/device/);
    expect(() => parseMeasure(JSON.stringify({ ...ok, verdict: "maybe" }))).toThrow(/verdict/);
  });
});
