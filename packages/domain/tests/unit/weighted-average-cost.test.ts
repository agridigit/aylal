import { describe, it } from "vitest";
import * as mod from "../../src/weighted-average-cost";
import { check, load, type Mod } from "./_f8";

const vectors = load("f8_wac.json");

describe("F8 weighted average cost (shared vectors f8_wac.json)", () => {
  for (const v of vectors) {
    it(`given the vector '${v.name}' when applying ${v.fn} then the shared expectation holds`, () => {
      check(mod as unknown as Mod, v);
    });
  }
});
