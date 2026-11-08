import { buildStatusDetail } from "../viewModels/statusDetailViewModel";

const NOW = "2026-12-05T12:00:00Z";
const status = (color: string, items: unknown[], over: Record<string, unknown> = {}) => ({
  parcel_id: "p1", color, reason_key: "status.frost", computed_at: NOW, data_age_at: NOW, imagery_reliability: "ok", items, ...over,
});
const item = (source: string, severity = "act") => ({ source, severity, reason_key: `status.${source}`, observed_at: NOW });

describe("status detail view model (R5-A3, R5-A4, R5-A5, SC-007)", () => {
  it("given an orange or red status then every contributor shows its source label key and its reason", () => {
    const d = buildStatusDetail(status("red", [item("weather_alert"), item("overdue_operations", "watch")]), NOW);
    expect(d.contributors).toEqual([
      expect.objectContaining({ source: "weather_alert", sourceLabelKey: "monitoring.source.weather_alert", reasonKey: "status.weather_alert", severity: "act" }),
      expect.objectContaining({ source: "overdue_operations", sourceLabelKey: "monitoring.source.overdue_operations", severity: "watch" }),
    ]);
  });

  it("given a green status then it says nothing to do with no contributor", () => {
    const d = buildStatusDetail(status("green", [], { reason_key: "status.nothing_to_do" }), NOW);
    expect(d).toMatchObject({ color: "green", reasonKey: "status.nothing_to_do", contributors: [] });
  });

  it("given an unavailable source (irrigation or health not delivered) then no item and no error are shown for it", () => {
    const d = buildStatusDetail(status("orange", [item("weather_alert", "watch")]), NOW);
    expect(d.contributors.map((c) => c.source)).toEqual(["weather_alert"]);
    expect(d.unavailableSources).toEqual([]);
  });

  it("given an unknown future source then it is shown with a generic source label instead of failing", () => {
    const d = buildStatusDetail(status("orange", [item("soil_probe", "watch")]), NOW);
    expect(d.contributors[0].sourceLabelKey).toBe("monitoring.source.other");
  });

  it("given unreliable imagery then the detail says the status rests on weather and observations", () => {
    expect(buildStatusDetail(status("green", [], { imagery_reliability: "low" }), NOW).imageryLow).toBe(true);
  });

  it("given an offline status older than 24 hours then its age is shown as stale with the date", () => {
    const old = "2026-12-03T12:00:00Z";
    expect(buildStatusDetail(status("red", [item("weather_alert")], { computed_at: old, data_age_at: old }), NOW).freshness).toMatchObject({ state: "stale", fetchedAt: old });
  });
});
