import { createYearCompareViewModel } from "../viewModels/yearCompareViewModel";

const pt = (day: number, date: string, vigor: number) => ({ day_of_campaign: day, acquired_on: date, vigor, plant_moisture: 0.4 });
const current = [pt(10, "2026-09-11", 0.5), pt(20, "2026-09-21", 0.7)];
const previous = [pt(10, "2025-09-11", 0.2), pt(30, "2025-10-01", 0.6)];

describe("year comparison view model (R6-A1, R6-A2)", () => {
  it("given a reference then both curves are read on the same campaign days", async () => {
    const vm = createYearCompareViewModel({ read: async () => ({ reference_available: true, current, previous }) });
    const s = await vm.load("f1", "p1");
    expect(s.state).toBe("ready");
    if (s.state !== "ready") return;
    expect(s.rows.map((r) => r.day)).toEqual([10, 20, 30]);
    expect(s.rows[0]).toMatchObject({ current: 0.5, previous: 0.2 });
  });

  it("given a day between two valid points of a curve then it is interpolated, and outside them nothing is extrapolated", async () => {
    const vm = createYearCompareViewModel({ read: async () => ({ reference_available: true, current, previous }) });
    const s = await vm.load("f1", "p1");
    if (s.state !== "ready") throw new Error("not ready");
    expect(s.rows[1]?.previous).toBeCloseTo(0.4, 10);
    expect(s.rows[2]?.current).toBeNull();
  });

  it("given no reference then a message key explains the absence and no empty previous curve is built", async () => {
    const vm = createYearCompareViewModel({ read: async () => ({ reference_available: false, current, previous: [] }) });
    const s = await vm.load("f1", "p1");
    expect(s).toMatchObject({ state: "no_reference", messageKey: "monitoring.compare.no_reference" });
    expect(s).not.toHaveProperty("previous");
    expect(s).not.toHaveProperty("rows");
  });

  it("given no data at all then the state is empty, never a blank chart", async () => {
    const vm = createYearCompareViewModel({ read: async () => ({ reference_available: false, current: [], previous: [] }) });
    expect((await vm.load("f1", "p1")).state).toBe("empty");
  });

  it("given nothing available then the state is unavailable and no value is invented", async () => {
    const vm = createYearCompareViewModel({ read: async () => null });
    expect((await vm.load("f1", "p1")).state).toBe("unavailable");
  });

  it("given a failing read then the error is surfaced for the error state", async () => {
    const vm = createYearCompareViewModel({ read: async () => { throw new Error("net"); } });
    await expect(vm.load("f1", "p1")).rejects.toThrow("net");
  });

  it("given two curves of 200 points then the chart keeps at most 2 x 200 points and never shows technical names", async () => {
    const many = (y: number) => Array.from({ length: 200 }, (_, i) => pt(i, `${y}-01-01`, 0.5));
    const vm = createYearCompareViewModel({ read: async () => ({ reference_available: true, current: many(2026), previous: many(2025) }) });
    const s = await vm.load("f1", "p1");
    if (s.state !== "ready") throw new Error("not ready");
    expect(s.rows.length).toBeLessThanOrEqual(400);
    expect(JSON.stringify(s).toLowerCase()).not.toMatch(/ndvi|ndmi/);
  });
});
