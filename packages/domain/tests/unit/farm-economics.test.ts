import { describe, it } from "vitest";
import * as mod from "../../src/farm-economics";
import { check, load, type Mod } from "./_f8";

const vectors = load("f8_economics.json");

describe("F8 parcel and farm economics (shared vectors f8_economics.json)", () => {
  for (const v of vectors) {
    it(`given the vector '${v.name}' when applying ${v.fn} then the shared expectation holds`, () => {
      check(mod as unknown as Mod, v);
    });
  }
});

import { expect } from "vitest";
import { pick } from "./_f8";

describe("F8 margin is the sum of the lines (R3-A1, SC-002)", () => {
  it("given random lines when computing then margin equals revenue minus expenses exactly", () => {
    const f = pick(mod as unknown as Mod, "parcel_economics");
    let seed = 11;
    const rnd = (n: number): number => {
      seed = (seed * 1103515245 + 12345) % 2147483648;
      return seed % n;
    };
    for (let i = 0; i < 200; i++) {
      const exp = Array.from({ length: rnd(8) }, () => rnd(2_000_000) - 500_000);
      const sal = Array.from({ length: rnd(8) }, () => rnd(2_000_000));
      const out = f({ expense_lines_cents: exp, sale_lines_cents: sal, harvested_milli: rnd(3) * 100000, area_m2: 1000 + rnd(50000) });
      expect(out.expenses_cents).toBe(exp.reduce((a, b) => a + b, 0));
      expect(out.revenue_cents).toBe(sal.reduce((a, b) => a + b, 0));
      expect(out.margin_cents).toBe(out.revenue_cents - out.expenses_cents);
    }
  });
});
