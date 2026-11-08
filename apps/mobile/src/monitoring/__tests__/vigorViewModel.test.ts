import { buildVigorChart, createVigorViewModel } from "../viewModels/vigorViewModel";

const pt = (d: string, v = 0.6, m = 0.4, clear = 95) => ({ acquired_on: d, vigor: v, plant_moisture: m, clear_pct: clear });

describe("vigor view model (R3-A2, R3-A3, R3-A4)", () => {
  it("given a series then the curve points are ordered by date and named vigor and plant moisture, never by technical names", () => {
    const chart = buildVigorChart([pt("2026-03-10"), pt("2026-01-10"), pt("2026-02-10")]);
    expect(chart.points.map((p) => p.date)).toEqual(["2026-01-10", "2026-02-10", "2026-03-10"]);
    expect(chart.seriesKeys).toEqual(["monitoring.vigor", "monitoring.plant_moisture"]);
    expect(JSON.stringify(chart).toLowerCase()).not.toMatch(/ndvi|ndmi/);
  });

  it("given more than 400 points then the curve is capped at 400 and keeps the most recent", () => {
    const many = Array.from({ length: 450 }, (_, i) => pt(new Date(Date.UTC(2025, 0, 1 + i)).toISOString().slice(0, 10)));
    const chart = buildVigorChart(many);
    expect(chart.points).toHaveLength(400);
    expect(chart.points[399].date).toBe(many[449].acquired_on);
  });

  it("given a point under 80 percent clear sky then it is never charted", () => {
    expect(buildVigorChart([pt("2026-01-10", 0.5, 0.4, 79.9), pt("2026-01-15", 0.6, 0.4, 80)]).points.map((p) => p.date)).toEqual(["2026-01-15"]);
  });

  it("given a recent cloudy scene rejected and an older valid map then the last valid map stays shown with its date", async () => {
    const vm = createVigorViewModel({ read: async () => ({ points: [pt("2026-01-10")], reliability: "ok", last_valid_map: { map_id: "m1", acquired_on: "2026-01-10" }, processing: false }) });
    const s = await vm.load("f1", "p1");
    expect(s.state).toBe("ready");
    expect(s.map).toEqual({ mapId: "m1", acquiredOn: "2026-01-10" });
  });

  it("given a parcel under 0.3 ha or in a greenhouse then imagery is flagged unreliable", async () => {
    const vm = createVigorViewModel({ read: async () => ({ points: [pt("2026-01-10")], reliability: "low", last_valid_map: null, processing: false }) });
    expect((await vm.load("f1", "p1")).lowReliability).toBe(true);
  });

  it("given a new parcel with the initial processing running then the empty state explains it", async () => {
    const vm = createVigorViewModel({ read: async () => ({ points: [], reliability: "ok", last_valid_map: null, processing: true }) });
    expect(await vm.load("f1", "p1")).toMatchObject({ state: "empty", emptyReasonKey: "monitoring.vigor.processing" });
  });

  it("given no valid image because of clouds then the empty state explains clouds", async () => {
    const vm = createVigorViewModel({ read: async () => ({ points: [], reliability: "ok", last_valid_map: null, processing: false }) });
    expect(await vm.load("f1", "p1")).toMatchObject({ state: "empty", emptyReasonKey: "monitoring.vigor.no_valid_image" });
  });

  it("given a failing store then the error is surfaced", async () => {
    const vm = createVigorViewModel({ read: async () => { throw new Error("db"); } });
    await expect(vm.load("f1", "p1")).rejects.toThrow("db");
  });
});
