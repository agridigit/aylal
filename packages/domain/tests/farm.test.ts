import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { validateFarm } from "../src/farm";

type V = { name: string; rule: string; input: unknown; expect: { valid: boolean; errors: { field: string; code: string }[] } };
const vectors: V[] = (JSON.parse(readFileSync(new URL("../vectors/f1_validation.json", import.meta.url), "utf-8")) as V[]).filter(
  (v) => v.rule === "farm",
);
const key = (e: { field: string; code: string }[]) => [...e].map((x) => x.field + ":" + x.code).sort();

describe("farm validation", () => {
  for (const v of vectors) {
    it(v.name, () => {
      const got = validateFarm(v.input);
      expect(got.valid).toBe(v.expect.valid);
      expect(key(got.errors)).toEqual(key(v.expect.errors));
    });
  }
});
