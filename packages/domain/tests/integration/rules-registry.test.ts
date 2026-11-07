import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { RULES, validate } from "../../src/validation";

describe("domain rules registry against shared vectors (AC3.5)", () => {
  it("Given the shared vector files, When reading them, Then every rule they name is registered", () => {
    for (const f of ["trial_record.json", "parcel.json"]) {
      const raw = JSON.parse(readFileSync(join(__dirname, "..", "..", "vectors", f), "utf8"));
      for (const c of raw as { rule: string }[]) expect(Object.keys(RULES), f).toContain(c.rule);
    }
  });

  it("Given an unknown rule, When validating, Then it throws", () => {
    expect(() => validate("nope.create", {})).toThrow(/unknown rule/);
  });

  it("Given an empty input, When validating each rule, Then the verdict is invalid with named fields", () => {
    for (const rule of Object.keys(RULES)) {
      const v = validate(rule, {});
      expect(v.valid, rule).toBe(false);
      expect(v.errors.length, rule).toBeGreaterThan(0);
    }
  });
});
