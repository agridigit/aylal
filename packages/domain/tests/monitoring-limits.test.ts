import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { LIMITS, withinLimit } from "../src/monitoring-limits";

const vectors: { rule: string; value: number; valid: boolean }[] = JSON.parse(
  readFileSync(new URL("../vectors/f3_limits.json", import.meta.url), "utf-8"),
);

describe("F3 monitoring limits (G4)", () => {
  for (const v of vectors) {
    it(`given rule ${v.rule} when the value is ${v.value} then validity is ${v.valid}`, () => {
      expect(withinLimit(v.rule, v.value)).toBe(v.valid);
    });
  }
  it("given the limits then the page default is 50 and the maximum 100", () => {
    expect(LIMITS.pageDefault).toBe(50);
    expect(LIMITS.pageMax).toBe(100);
  });
  it("given an unknown rule then it is refused", () => {
    expect(withinLimit("nope", 1)).toBe(false);
  });
});
