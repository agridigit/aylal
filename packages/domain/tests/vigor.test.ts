import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { alignToCampaignDays, campaignDay, campaignStart, isScenePublishable } from "../src/vigor";

const v: { clear_pct: number; publishable: boolean }[] = JSON.parse(readFileSync(new URL("../vectors/f3_cloud_rule.json", import.meta.url), "utf-8"));

describe("F3 80 % clear-sky rule (FR-007)", () => {
  for (const c of v) {
    it(`given ${c.clear_pct} % clear when publishing then ${c.publishable}`, () => {
      expect(isScenePublishable(c.clear_pct)).toBe(c.publishable);
    });
  }
});

const pt = (acquired_on: string, vigor: number, plant_moisture = 0.5) => ({ acquired_on, vigor, plant_moisture });

describe("F3 campaign start (R6-A1, research 20)", () => {
  it("given a season start then the campaign starts on that date, not on 1 September", () => {
    expect(campaignStart("2026-03-15", "2026-11-08")).toBe("2026-03-15");
  });
  it("given no season then the campaign starts on the last 1 September", () => {
    expect(campaignStart(null, "2026-11-08")).toBe("2026-09-01");
    expect(campaignStart(null, "2026-03-01")).toBe("2025-09-01");
    expect(campaignStart(null, "2026-09-01")).toBe("2026-09-01");
  });
  it("given two dates then the campaign day counts whole days from the start, across a leap day", () => {
    expect(campaignDay("2025-09-01", "2025-09-01")).toBe(0);
    expect(campaignDay("2025-09-01", "2025-09-11")).toBe(10);
    expect(campaignDay("2023-12-31", "2024-03-01")).toBe(61);
  });
});

describe("F3 year comparison alignment (R6-A1)", () => {
  const points = [pt("2025-09-11", 0.2), pt("2025-09-21", 0.4)];
  it("given a day between two valid points then the value is interpolated linearly", () => {
    expect(alignToCampaignDays(points, "2025-09-01", [15])[0]?.vigor).toBeCloseTo(0.3, 10);
  });
  it("given a day on a point then the point value is kept", () => {
    expect(alignToCampaignDays(points, "2025-09-01", [10, 20]).map((p) => p.vigor)).toEqual([0.2, 0.4]);
  });
  it("given a day before the first or after the last point then there is no value and nothing is extrapolated", () => {
    expect(alignToCampaignDays(points, "2025-09-01", [5, 25]).map((p) => p.vigor)).toEqual([null, null]);
  });
  it("given the same campaign days for two years then both curves are read on the same days", () => {
    const days = [10, 20];
    const now = alignToCampaignDays([pt("2026-09-11", 0.5), pt("2026-09-21", 0.7)], "2026-09-01", days);
    const before = alignToCampaignDays(points, "2025-09-01", days);
    expect(now.map((p) => p.day)).toEqual(before.map((p) => p.day));
  });
  it("given no point then every day is empty, never zero", () => {
    expect(alignToCampaignDays([], "2025-09-01", [3]).map((p) => p.vigor)).toEqual([null]);
  });
  it("given unordered points then the result does not depend on the input order", () => {
    expect(alignToCampaignDays([...points].reverse(), "2025-09-01", [15])[0]?.vigor).toBeCloseTo(0.3, 10);
  });
});
