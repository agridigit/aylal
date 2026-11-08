import { describe, it } from "vitest";
import * as mod from "../../src/receipt-proposal";
import { check, load, type Mod } from "./_f8";

const vectors = load("f8_receipt.json");

describe("F8 receipt proposal bounds (shared vectors f8_receipt.json)", () => {
  for (const v of vectors) {
    it(`given the vector '${v.name}' when applying ${v.fn} then the shared expectation holds`, () => {
      check(mod as unknown as Mod, v);
    });
  }
});
