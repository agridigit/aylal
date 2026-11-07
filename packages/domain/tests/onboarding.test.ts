import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { nextOnboardingStep, validateProfile } from "../src/onboarding";

type V = { name: string; rule: string; input: unknown; expect: { valid: boolean; errors: { field: string; code: string }[] } };
const profiles: V[] = (JSON.parse(readFileSync(new URL("../vectors/f1_validation.json", import.meta.url), "utf-8")) as V[]).filter(
  (v) => v.rule === "profile",
);
const key = (e: { field: string; code: string }[]) => e.map((x) => x.field + ":" + x.code).sort();

describe("profile validation", () => {
  for (const v of profiles) {
    it(v.name, () => {
      const got = validateProfile(v.input);
      expect(got.valid).toBe(v.expect.valid);
      expect(key(got.errors)).toEqual(key(v.expect.errors));
    });
  }
});

describe("onboarding order", () => {
  const base = { language: null, phoneVerified: false, consentGiven: false, displayName: null, hasFarm: false };
  it("given a fresh device when starting then language is asked first", () => {
    expect(nextOnboardingStep(base)).toBe("language");
  });
  it("given a language when no phone verified then phone is next", () => {
    expect(nextOnboardingStep({ ...base, language: "fr" })).toBe("phone");
  });
  it("given a verified phone when no consent then consent comes before the profile", () => {
    expect(nextOnboardingStep({ ...base, language: "fr", phoneVerified: true })).toBe("consent");
  });
  it("given consent when no name then the minimal profile is next", () => {
    expect(nextOnboardingStep({ ...base, language: "ary", phoneVerified: true, consentGiven: true })).toBe("profile");
  });
  it("given a profile when no farm then farm creation is next", () => {
    expect(
      nextOnboardingStep({ language: "ar", phoneVerified: true, consentGiven: true, displayName: "H", hasFarm: false }),
    ).toBe("farm");
  });
  it("given everything done then onboarding is done", () => {
    expect(
      nextOnboardingStep({ language: "ar", phoneVerified: true, consentGiven: true, displayName: "H", hasFarm: true }),
    ).toBe("done");
  });
});
