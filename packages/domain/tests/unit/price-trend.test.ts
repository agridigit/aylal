import { describe, it } from "vitest";
import * as mod from "../../src/price-trend";
import { check, load, type Mod } from "./_f8";

const vectors = load("f8_trend.json");

describe("F8 price trend and staleness (shared vectors f8_trend.json)", () => {
  for (const v of vectors) {
    it(`given the vector '${v.name}' when applying ${v.fn} then the shared expectation holds`, () => {
      check(mod as unknown as Mod, v);
    });
  }
});
