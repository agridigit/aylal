import { describeFreshness } from "../staleness";

const NOW = "2026-12-05T12:00:00Z";
const ago = (h: number) => new Date(Date.parse(NOW) - h * 3_600_000).toISOString();

describe("data freshness shown on every dashboard screen (R1-A2, FR-017, SC-005)", () => {
  it("given data loaded 2 hours ago then it is fresh and carries its date", () => {
    expect(describeFreshness(ago(2), NOW)).toEqual({ state: "fresh", ageHours: 2, fetchedAt: ago(2) });
  });

  it("given offline data loaded 30 hours ago then it is stale but still shows its date", () => {
    expect(describeFreshness(ago(30), NOW)).toEqual({ state: "stale", ageHours: 30, fetchedAt: ago(30) });
  });

  it("given nothing ever loaded then the state is never, with no date and no age", () => {
    expect(describeFreshness(null, NOW)).toEqual({ state: "never", ageHours: null, fetchedAt: null });
  });
});
