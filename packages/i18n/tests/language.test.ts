import { describe, expect, it } from "vitest";
import { applyLanguage, createI18n, flattenKeys, LANGUAGE_OPTIONS, resources } from "../src/index";

describe("language choice (R2)", () => {
  it("Given the first launch, When listing the options, Then darija, arabic and french are offered in that order", () => {
    expect(LANGUAGE_OPTIONS.map((o) => o.code)).toEqual(["ary", "ar", "fr"]);
  });

  it("Given each option, When read aloud, Then it has a label and a spoken text in its own language", () => {
    for (const o of LANGUAGE_OPTIONS) {
      expect(o.label.trim()).not.toBe("");
      expect(o.spokenText.trim()).not.toBe("");
      expect(o.speechLocale).toMatch(/^(ar|fr)/);
    }
  });

  it("Given the options, When checking direction, Then ary and ar are rtl and fr is ltr", () => {
    const dir = Object.fromEntries(LANGUAGE_OPTIONS.map((o) => [o.code, o.dir]));
    expect(dir).toEqual({ ary: "rtl", ar: "rtl", fr: "ltr" });
  });

  it("Given a validated choice, When applying it, Then texts and direction switch immediately", async () => {
    const i18n = createI18n("fr");
    const fr = i18n.t("onboarding.language.title");
    expect(fr).not.toBe("onboarding.language.title");
    const state = await applyLanguage(i18n, "ar");
    expect(state).toEqual({ locale: "ar", rtl: true });
    expect(i18n.t("onboarding.language.title")).not.toBe(fr);
    expect((await applyLanguage(i18n, "fr")).rtl).toBe(false);
  });

  it("Given an unknown language, When applying it, Then it is refused and the current language is kept", async () => {
    const i18n = createI18n("ary");
    await expect(applyLanguage(i18n, "en")).rejects.toThrow();
    expect(i18n.locale).toBe("ary");
  });

  it("Given the onboarding texts, When comparing locales, Then every key exists and is filled in all of them", () => {
    const keys = Object.keys(flattenKeys(resources.fr)).filter((k) => k.startsWith("onboarding.language."));
    expect(keys.length).toBeGreaterThan(0);
    for (const loc of ["ary", "ary-Latn", "ar"] as const) {
      const flat = flattenKeys(resources[loc]);
      for (const k of keys) expect(flat[k]?.trim(), `${loc}:${k}`).toBeTruthy();
    }
  });
});
