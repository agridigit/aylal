import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { normalizePhone } from "../src/phone";

const vectors: { name: string; input: string; expect: string | null }[] = JSON.parse(
  readFileSync(new URL("../vectors/f1_phone.json", import.meta.url), "utf-8"),
);

describe("Moroccan phone format", () => {
  for (const v of vectors) {
    it(`given ${v.input || "empty"} when normalising then ${v.name}`, () => {
      expect(normalizePhone(v.input)).toBe(v.expect);
    });
  }
});
