import { describe, expect, it } from "vitest";
import { resolveTextLayout } from "../src/text-layout";

const LONG_FR = "Vérification de la synchronisation des parcelles et des interventions saisies hors ligne depuis la dernière connexion au serveur. ".repeat(3);
const SHORT_AR = "حقل";

describe("text layout edge cases", () => {
  it("Given a long French text, When laid out, Then it wraps without overflow and is never cut to one line", () => {
    const l = resolveTextLayout({ text: LONG_FR, locale: "fr" });
    expect(l.direction).toBe("ltr");
    expect(l.wrap).toBe(true);
    expect(l.shrinkable).toBe(true);
    expect(l.maxLines === null || l.maxLines >= 2).toBe(true);
    if (l.maxLines !== null) expect(l.ellipsizeMode).toBe("tail");
  });

  it("Given a short Arabic text, When laid out, Then it is RTL, aligned to start and uses the Arabic font", () => {
    const l = resolveTextLayout({ text: SHORT_AR, locale: "ar" });
    expect(l.direction).toBe("rtl");
    expect(l.textAlign).toBe("start");
    expect(l.fontFamily).toBe("IBM Plex Sans Arabic");
    expect(l.wrap).toBe(true);
  });
});
