import { sessionTraffic, withinTrafficBudget, TRAFFIC_BUDGET_BYTES } from "../trafficBudget";

const MB = 1024 * 1024;

describe("daily traffic budget (SC-006)", () => {
  it("Given the budget, When reading it, Then it is 5 MB per day", () => {
    expect(TRAFFIC_BUDGET_BYTES).toBe(5 * MB);
  });

  it("Given a typical session of sync and API calls, When summing, Then the total is under 5 MB", () => {
    const requests = [
      { kind: "sync", bytesIn: 800_000, bytesOut: 200_000 },
      { kind: "api", bytesIn: 120_000, bytesOut: 30_000 },
      { kind: "telemetry", bytesIn: 1_000, bytesOut: 40_000 },
    ];
    expect(sessionTraffic(requests)).toBe(1_191_000);
    expect(withinTrafficBudget(requests)).toBe(true);
  });

  it("Given a session over 5 MB, When checking, Then the budget is exceeded", () => {
    expect(withinTrafficBudget([{ kind: "sync", bytesIn: 5 * MB, bytesOut: 1 }])).toBe(false);
  });

  it("Given satellite imagery, When on mobile data, Then it is not fetched automatically", () => {
    expect(withinTrafficBudget([{ kind: "satellite", bytesIn: 10, bytesOut: 0, wifi: false, onDemand: false }])).toBe(false);
  });
});
