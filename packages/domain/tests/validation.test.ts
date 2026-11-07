import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { validate } from "../src/validation";

type Vector = {
  name: string;
  rule: string;
  input: unknown;
  expect: { valid: boolean; errors: { field: string; code: string }[] };
};

const load = (f: string): Vector[] =>
  JSON.parse(readFileSync(new URL(`../vectors/${f}`, import.meta.url), "utf-8"));

const sortErrors = (e: { field: string; code: string }[]) =>
  [...e].sort((a, b) => (a.field + a.code).localeCompare(b.field + b.code));

for (const file of ["trial_record.json", "parcel.json"]) {
  describe(`shared validation vectors: ${file}`, () => {
    for (const v of load(file)) {
      it(`${v.rule}: ${v.name}`, () => {
        const verdict = validate(v.rule, v.input);
        expect(verdict.valid).toBe(v.expect.valid);
        expect(sortErrors(verdict.errors)).toEqual(sortErrors(v.expect.errors));
      });
    }
  });
}
