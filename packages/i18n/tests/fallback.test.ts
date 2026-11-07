import { describe, expect, it } from "vitest";
import { createI18n, isRtl, resolveLocale } from "../src/index";

describe("i18n fallback and switching (FR-007)", () => {
  it("Given an unsupported device language, When resolving, Then it falls back to fr", () => {
    expect(resolveLocale("es-ES")).toBe("fr");
    expect(resolveLocale("zz")).toBe("fr");
    expect(resolveLocale(undefined)).toBe("fr");
    expect(resolveLocale("")).toBe("fr");
  });

  it("Given a supported device language, When resolving, Then it is kept", () => {
    expect(resolveLocale("fr-FR")).toBe("fr");
    expect(resolveLocale("ar-MA")).toBe("ar");
    expect(resolveLocale("ary")).toBe("ary");
    expect(resolveLocale("ary-Latn")).toBe("ary-Latn");
  });

  it("Given a locale, When asking for direction, Then ary and ar are RTL and ary-Latn and fr are LTR", () => {
    expect(isRtl("ary")).toBe(true);
    expect(isRtl("ar")).toBe(true);
    expect(isRtl("ary-Latn")).toBe(false);
    expect(isRtl("fr")).toBe(false);
  });

  it("Given a running app, When the language changes at any time, Then texts switch immediately", async () => {
    const i18n = createI18n("fr");
    const fr = i18n.t("home.title");
    expect(fr).not.toBe("home.title");
    await i18n.changeLanguage("ar");
    expect(i18n.locale).toBe("ar");
    expect(i18n.t("home.title")).not.toBe(fr);
    await i18n.changeLanguage("fr");
    expect(i18n.t("home.title")).toBe(fr);
  });

  it("Given an unknown key, When translating, Then the key itself is returned and nothing throws", () => {
    expect(createI18n("ar").t("nope.missing")).toBe("nope.missing");
  });
});
