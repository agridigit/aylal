import { describe, it } from "vitest";
import * as mod from "../../src/stock-ledger";
import { check, load, type Mod } from "./_f8";

const vectors = load("f8_stock.json");

describe("F8 stock ledger (shared vectors f8_stock.json)", () => {
  for (const v of vectors) {
    it(`given the vector '${v.name}' when applying ${v.fn} then the shared expectation holds`, () => {
      check(mod as unknown as Mod, v);
    });
  }
});
