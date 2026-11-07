import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { LIMITS, withinLimit } from "../src/operation-limits";

const vectors: { rule: string; value: number | string; valid: boolean; today: string }[] = JSON.parse(
  readFileSync(new URL("../vectors/f6_limits.json", import.meta.url), "utf-8"),
);

describe("F6 operation limits (G3)", () => {
  for (const v of vectors) {
    it(`given rule ${v.rule} when the value is ${v.value} then validity is ${v.valid}`, () => {
      expect(withinLimit(v.rule, v.value, v.today)).toBe(v.valid);
    });
  }
  it("given the limits then the pagination default is 50 and the sync batch is 100", () => {
    expect(LIMITS.pageDefault).toBe(50);
    expect(LIMITS.batch).toBe(100);
  });
  it("given an unknown rule then it is refused", () => {
    expect(withinLimit("nope", 1, "2026-11-07")).toBe(false);
  });
});
