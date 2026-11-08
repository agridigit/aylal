import { describe, expect, it } from "vitest";
import { staleness, STALE_AFTER_HOURS } from "../src/staleness";

const NOW = "2026-12-05T12:00:00Z";
const ago = (h: number) => new Date(Date.parse(NOW) - h * 3_600_000).toISOString();

describe("F3 data staleness (R1-A2, FR-017: the age of the data is always visible)", () => {
  it("given the product rule then data older than 24 hours is stale", () => {
    expect(STALE_AFTER_HOURS).toBe(24);
  });

  it("given data fetched 3 hours ago when computing then it is fresh and the age is 3 hours", () => {
    expect(staleness(ago(3), NOW)).toEqual({ ageHours: 3, stale: false });
  });

  it("given data fetched exactly 24 hours ago when computing then it is still fresh", () => {
    expect(staleness(ago(24), NOW).stale).toBe(false);
  });

  it("given data fetched 25 hours ago when computing then it is stale", () => {
    expect(staleness(ago(25), NOW)).toEqual({ ageHours: 25, stale: true });
  });

  it("given no data ever loaded when computing then it is stale with no age and no invented date", () => {
    expect(staleness(null, NOW)).toEqual({ ageHours: null, stale: true });
  });

  it("given a date in the future (clock drift) when computing then the age is never negative", () => {
    expect(staleness(ago(-2), NOW).ageHours).toBe(0);
  });

  it("given a custom threshold when computing then it is honoured", () => {
    expect(staleness(ago(5), NOW, 4).stale).toBe(true);
  });
});
