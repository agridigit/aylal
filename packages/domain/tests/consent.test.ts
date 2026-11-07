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

import { CONSENT_PURPOSE_DATA_POLICY, hasActiveConsent } from "../src/consent";

describe("versioned consent (R3-A2)", () => {
  const grant = { purpose: CONSENT_PURPOSE_DATA_POLICY, text_version: "2026-01", withdrawn_at: null };
  it("Given no grant, When checking, Then the user may not proceed", () => {
    expect(hasActiveConsent([], CONSENT_PURPOSE_DATA_POLICY, "2026-01")).toBe(false);
  });
  it("Given a grant of the current text version, When checking, Then it is active", () => {
    expect(hasActiveConsent([grant], CONSENT_PURPOSE_DATA_POLICY, "2026-01")).toBe(true);
  });
  it("Given a grant of an older text version, When checking, Then a new consent is required", () => {
    expect(hasActiveConsent([grant], CONSENT_PURPOSE_DATA_POLICY, "2026-06")).toBe(false);
  });
  it("Given a withdrawn grant, When checking, Then it is not active", () => {
    expect(hasActiveConsent([{ ...grant, withdrawn_at: "2026-02-01T00:00:00Z" }], CONSENT_PURPOSE_DATA_POLICY, "2026-01")).toBe(false);
  });
});
