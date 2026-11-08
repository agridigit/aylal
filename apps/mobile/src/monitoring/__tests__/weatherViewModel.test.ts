import { createWeatherViewModel } from "../viewModels/weatherViewModel";

const NOW = "2026-12-05T12:00:00Z";
const day = (i: number) => ({ date: `2026-12-${String(5 + i).padStart(2, "0")}`, tmin: 5 + i, tmax: 18 + i, rain_mm: i, wind_kmh: 10 + i, humidity_pct: 50 + i, icon: "sun" });
const eight = Array.from({ length: 8 }, (_, i) => day(i));
const ago = (h: number) => new Date(Date.parse(NOW) - h * 3_600_000).toISOString();

describe("weather view model (R1-A1, R1-A2, edge cases)", () => {
  it("given a located farm with a fresh forecast then today and the 7 next days show temperature, rain, wind, humidity and an icon", async () => {
    const vm = createWeatherViewModel({ read: async () => ({ availability: "ok", reason: null, fetched_at: ago(1), days: eight }) }, () => NOW);
    const s = await vm.load("f1");
    expect(s.state).toBe("ready");
    expect(s.days).toHaveLength(8);
    expect(s.days[0]).toMatchObject({ date: "2026-12-05", tmin: 5, tmax: 18, rainMm: 0, windKmh: 10, humidityPct: 50, icon: "sun" });
  });

  it("given no network and a forecast loaded 30 hours ago then the last data shows with its date and the stale flag", async () => {
    const vm = createWeatherViewModel({ read: async () => ({ availability: "ok", reason: null, fetched_at: ago(30), days: eight }) }, () => NOW);
    const s = await vm.load("f1");
    expect(s.state).toBe("ready");
    expect(s).toMatchObject({ stale: true, fetchedAt: ago(30) });
    expect(s.days).toHaveLength(8);
  });

  it("given a farm without location then the screen invites to set the location and shows no value", async () => {
    const vm = createWeatherViewModel({ read: async () => ({ availability: "unavailable", reason: "farm_not_located", fetched_at: null, days: [] }) }, () => NOW);
    const s = await vm.load("f1");
    expect(s.state).toBe("not_located");
    expect(s.days).toEqual([]);
  });

  it("given an unconfigured gateway and no earlier forecast then it is unavailable and no value is invented", async () => {
    const vm = createWeatherViewModel({ read: async () => ({ availability: "unavailable", reason: "gateway_not_configured", fetched_at: null, days: [] }) }, () => NOW);
    const s = await vm.load("f1");
    expect(s).toMatchObject({ state: "unavailable", days: [], fetchedAt: null });
  });

  it("given an unavailable gateway but an older forecast then the dated last forecast is kept", async () => {
    const vm = createWeatherViewModel({ read: async () => ({ availability: "unavailable", reason: "gateway_unreachable", fetched_at: ago(10), days: eight }) }, () => NOW);
    const s = await vm.load("f1");
    expect(s.state).toBe("unavailable");
    expect(s.days).toHaveLength(8);
    expect(s.fetchedAt).toBe(ago(10));
  });

  it("given nothing stored locally then it reads as loading-empty, never as zeros", async () => {
    const vm = createWeatherViewModel({ read: async () => null }, () => NOW);
    const s = await vm.load("f1");
    expect(s).toMatchObject({ state: "unavailable", days: [], fetchedAt: null });
  });

  it("given a failing store then the error is surfaced for the error state", async () => {
    const vm = createWeatherViewModel({ read: async () => { throw new Error("db"); } }, () => NOW);
    await expect(vm.load("f1")).rejects.toThrow("db");
  });

  it("given more than 8 days in the store then only today and 7 days are shown", async () => {
    const vm = createWeatherViewModel({ read: async () => ({ availability: "ok", reason: null, fetched_at: ago(1), days: [...eight, day(8), day(9)] }) }, () => NOW);
    expect((await vm.load("f1")).days).toHaveLength(8);
  });
});
