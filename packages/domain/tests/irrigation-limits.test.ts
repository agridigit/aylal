import { describe, expect, it } from "vitest";
import { LIMITS, withinLimit } from "../src/irrigation-limits";
import { readFileSync } from "node:fs";

const rows: { rule: string; value: number; valid: boolean }[] = JSON.parse(
  readFileSync(new URL("../vectors/f4_limits.json", import.meta.url), "utf-8"),
);

describe("F4 irrigation limits (G4, shared vectors f4_limits.json)", () => {
  for (const v of rows) {
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
