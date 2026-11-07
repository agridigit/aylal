import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { convertDose } from "../src/units";

const vectors: { value: number; from: string; to: string; expected: number | null }[] = JSON.parse(
  readFileSync(new URL("../vectors/f6_units.json", import.meta.url), "utf-8"),
);

describe("F6 dose unit conversion", () => {
  for (const v of vectors) {
    it(`given ${v.value} ${v.from} when converting to ${v.to} then ${v.expected}`, () => {
      expect(convertDose(v.value, v.from, v.to)).toBe(v.expected);
    });
  }
});
