import { describe, it } from "vitest";
import * as mod from "../../src/money";
import { check, load, type Mod } from "./_f8";

const vectors = load("f8_money.json");

describe("F8 money (integer cents, half-up rounding) (shared vectors f8_money.json)", () => {
  for (const v of vectors) {
    it(`given the vector '${v.name}' when applying ${v.fn} then the shared expectation holds`, () => {
      check(mod as unknown as Mod, v);
    });
  }
});
