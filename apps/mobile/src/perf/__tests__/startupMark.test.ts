import { createStartupMark, STARTUP_BUDGET_MS } from "../startupMark";

describe("startup mark (AC2.1)", () => {
  it("Given the app started, When Home is displayed, Then a mark with the elapsed time is emitted", () => {
    let t = 1000;
    const emitted: any[] = [];
    const m = createStartupMark({ now: () => t, emit: (e) => emitted.push(e) });
    m.appStarted();
    t = 1800;
    m.homeDisplayed();
    expect(emitted).toEqual([{ name: "home_displayed", durationMs: 800 }]);
  });

  it("Given Home re-rendered, When displayed again, Then the mark is emitted only once", () => {
    const emitted: any[] = [];
    const m = createStartupMark({ now: () => 0, emit: (e) => emitted.push(e) });
    m.appStarted();
    m.homeDisplayed();
    m.homeDisplayed();
    expect(emitted).toHaveLength(1);
  });

  it("Given the 3 s budget, When checking a duration, Then under 3000 ms passes and above fails", () => {
    expect(STARTUP_BUDGET_MS).toBe(3000);
    const m = createStartupMark({ now: () => 0, emit: () => {} });
    expect(m.withinBudget(2999)).toBe(true);
    expect(m.withinBudget(3001)).toBe(false);
  });
});
