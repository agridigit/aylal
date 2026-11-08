import { buildDashboard } from "../viewModels/dashboardViewModel";

const NOW = "2026-12-05T12:00:00Z";
const row = (id: string, color: string, over: Record<string, unknown> = {}) => ({
  parcel_id: id, name: id, color, reason_key: `status.${color}`, computed_at: NOW, imagery_reliability: "ok", contributors: 0, ...over,
});
const weather = { availability: "ok", reason: null, fetched_at: NOW, days: [] as unknown[] };

describe("dashboard view model (R5-A1, R1-A2, empty farm, 30 s overview)", () => {
  it("given several parcels then red come first, then orange, then green, each with colour and one-sentence reason key", () => {
    const d = buildDashboard([row("g", "green"), row("o", "orange"), row("r", "red")], weather, NOW);
    expect(d.parcels.map((p) => p.parcelId)).toEqual(["r", "o", "g"]);
    expect(d.parcels[0]).toMatchObject({ color: "red", reasonKey: "status.red" });
  });

  it("given equal colours then more contributors first, then name", () => {
    const d = buildDashboard([row("b", "red", { contributors: 1 }), row("a", "red", { contributors: 1 }), row("c", "red", { contributors: 3 })], weather, NOW);
    expect(d.parcels.map((p) => p.parcelId)).toEqual(["c", "a", "b"]);
  });

  it("given parcels then the counters are computed from the listed rows only", () => {
    const d = buildDashboard([row("r1", "red"), row("r2", "red"), row("g", "green")], weather, NOW);
    expect(d.counts).toEqual({ red: 2, orange: 0, green: 1 });
  });

  it("given a farm without parcel then the weather stays visible and the screen invites to create a first parcel", () => {
    const d = buildDashboard([], weather, NOW);
    expect(d).toMatchObject({ state: "empty_no_parcel", counts: { red: 0, orange: 0, green: 0 } });
    expect(d.weather).toBe(weather);
  });

  it("given offline data older than 24 hours then the dashboard flags it stale and keeps the date", () => {
    const old = "2026-12-03T12:00:00Z";
    const d = buildDashboard([row("g", "green", { computed_at: old })], { ...weather, fetched_at: old }, NOW);
    expect(d.freshness).toMatchObject({ state: "stale", fetchedAt: old });
  });

  it("given parcels with low-reliability imagery then the flag is carried to the card", () => {
    expect(buildDashboard([row("s", "orange", { imagery_reliability: "low" })], weather, NOW).parcels[0].imageryLow).toBe(true);
  });

  it("given 200 parcels then building the dashboard stays under 2 seconds", () => {
    const colors = ["green", "orange", "red"];
    const rows = Array.from({ length: 200 }, (_, i) => row(`p${String(i).padStart(3, "0")}`, colors[i % 3], { contributors: i % 5 }));
    const t0 = Date.now();
    const d = buildDashboard(rows, weather, NOW);
    expect(Date.now() - t0).toBeLessThan(2000);
    expect(d.parcels).toHaveLength(200);
    expect(d.parcels[0].color).toBe("red");
  });
});
