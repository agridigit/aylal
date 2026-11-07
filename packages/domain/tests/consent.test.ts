import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { validateConsent } from "../src/consent";

type V = { name: string; rule: string; input: unknown; expect: { valid: boolean; errors: { field: string; code: string }[] } };
const vectors: V[] = (JSON.parse(readFileSync(new URL("../vectors/f1_validation.json", import.meta.url), "utf-8")) as V[]).filter(
  (v) => v.rule === "consent",
);
const key = (e: { field: string; code: string }[]) => [...e].map((x) => x.field + ":" + x.code).sort();

describe("consent validation", () => {
  for (const v of vectors) {
    it(v.name, () => {
      const got = validateConsent(v.input);
      expect(got.valid).toBe(v.expect.valid);
      expect(key(got.errors)).toEqual(key(v.expect.errors));
    });
  }
});
