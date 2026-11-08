import { describe, it } from "vitest";
import * as mod from "../../src/expense-allocation";
import { check, load, type Mod } from "./_f8";

const vectors = load("f8_allocation.json");

describe("F8 largest-remainder allocation (shared vectors f8_allocation.json)", () => {
  for (const v of vectors) {
    it(`given the vector '${v.name}' when applying ${v.fn} then the shared expectation holds`, () => {
      check(mod as unknown as Mod, v);
    });
  }
});

import { expect } from "vitest";
import { pick } from "./_f8";

describe("F8 allocation properties (SC-002)", () => {
  it("given many amounts and surfaces when allocating then the shares sum exactly to the amount and none is negative", () => {
    const allocate = pick(mod as unknown as Mod, "allocate");
    let seed = 7;
    const rnd = (n: number): number => {
      seed = (seed * 1103515245 + 12345) % 2147483648;
      return seed % n;
    };
    for (let i = 0; i < 300; i++) {
      const parcels = Array.from({ length: 1 + rnd(12) }, (_, j) => ({ id: `p${String(j).padStart(2, "0")}`, area_m2: 1 + rnd(90000) }));
      const amount = 1 + rnd(5_000_000);
      const out = allocate({ amount_cents: amount, parcels }) as { shares: { id: string; share_cents: number }[] };
      expect(out.shares.reduce((s, x) => s + x.share_cents, 0)).toBe(amount);
      expect(out.shares.every((x) => x.share_cents >= 0)).toBe(true);
    }
  });
  it("given the same input twice when allocating then the result is identical (deterministic tie-break)", () => {
    const allocate = pick(mod as unknown as Mod, "allocate");
    const input = { amount_cents: 10001, parcels: [{ id: "b", area_m2: 4 }, { id: "a", area_m2: 4 }, { id: "c", area_m2: 4 }] };
    expect(allocate(input)).toEqual(allocate(input));
  });
});
