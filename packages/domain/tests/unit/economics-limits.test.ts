import { describe, expect, it } from "vitest";
import * as limits from "../../src/economics-limits";
import { load, pick, type Mod } from "./_f8";

type Row = { rule: string; value: number; valid: boolean };
const rows = load<Row>("f8_limits.json");

describe("F8 caps (G4, shared vectors f8_limits.json)", () => {
  for (const v of rows) {
    it(`given rule ${v.rule} when the value is ${v.value} then validity is ${v.valid}`, () => {
      expect(pick(limits as unknown as Mod, "within_limit")(v.rule, v.value)).toBe(v.valid);
    });
  }
  it("given the constants then the photo cap is 6 MiB, the page default 50 and the maximum 100", () => {
    const L = (limits as unknown as { LIMITS?: Record<string, number> }).LIMITS;
    expect(L, "LIMITS is not exported").toBeDefined();
    expect(L!.photoBytes).toBe(6 * 1024 * 1024);
    expect([L!.pageDefault, L!.pageMax]).toEqual([50, 100]);
    expect(L!.syncBatch).toBe(100);
  });
  it("given an unknown rule then it is refused", () => {
    expect(pick(limits as unknown as Mod, "within_limit")("nope", 1)).toBe(false);
  });
});
