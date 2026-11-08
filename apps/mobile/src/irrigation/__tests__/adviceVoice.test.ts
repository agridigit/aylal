/** T055 (US2) - FR-020: the advice is read aloud from i18n keys (never hard-coded text), in the user's language, through the shared
 *  speech wrapper. The module does not exist yet: imported inside each test. */
const load = async () => await import("../adviceVoice");
const t = (key: string, params: Record<string, unknown> = {}) => `${key}|${JSON.stringify(params)}`;
const engine = () => {
  const calls: { text: string; language: string }[] = [];
  return { calls, stop: jest.fn(), speak: (text: string, o: { language: string }) => void calls.push({ text, language: o.language }) };
};
const base = { parcel_id: "p1", for_date: "2026-06-04", confidence: "medium", assumptions: [] as unknown[], sectors: [] as unknown[], is_last_known: false };

describe("advice voice (R2-A1, R2-A2, R2-A6, R2-A7)", () => {
  it("given an irrigate advice of 150 minutes when building the sentence then it uses the i18n key with hours and minutes", async () => {
    const { adviceSpeech } = await load();
    expect(adviceSpeech({ ...base, kind: "irrigate", total_minutes: 150 }, t)).toBe(t("advice.speech.irrigate", { hours: 2, minutes: 30 }));
  });

  it("given a postpone_rain advice when building the sentence then the rain key is used and no duration is spoken", async () => {
    const { adviceSpeech } = await load();
    expect(adviceSpeech({ ...base, kind: "postpone_rain", total_minutes: null }, t)).toBe(t("advice.speech.postpone_rain", {}));
  });

  it("given a no_need advice then the no-need key is used", async () => {
    const { adviceSpeech } = await load();
    expect(adviceSpeech({ ...base, kind: "no_need", total_minutes: null }, t)).toBe(t("advice.speech.no_need", {}));
  });

  it("given an unavailable advice then the reason is spoken through a key, never a number", async () => {
    const { adviceSpeech } = await load();
    expect(adviceSpeech({ ...base, kind: "unavailable", unavailable_reason: "no_system", total_minutes: null }, t)).toBe(t("advice.speech.unavailable", { reason: "no_system" }));
  });

  it("given a last known advice then its date is spoken with the reduced confidence", async () => {
    const { adviceSpeech } = await load();
    const out = adviceSpeech({ ...base, kind: "irrigate", total_minutes: 60, is_last_known: true, for_date: "2026-06-03", confidence: "low" }, t);
    expect(out).toContain("advice.speech.last_known");
    expect(out).toContain("2026-06-03");
  });

  it("given a rainfed stress advice then the stress level is spoken and no irrigation duration", async () => {
    const { adviceSpeech } = await load();
    expect(adviceSpeech({ ...base, kind: "rainfed_stress", stress_level: "high", total_minutes: null }, t)).toBe(t("advice.speech.rainfed_stress", { level: "high" }));
  });

  it.each([["ary", "ar-MA"], ["ar", "ar"], ["fr", "fr-FR"]])("given the locale %s when speaking then the device voice language is %s and any previous reading is stopped", async (locale, language) => {
    const { speakAdvice } = await load();
    const speech = engine();
    speakAdvice({ ...base, kind: "no_need", total_minutes: null }, locale as never, { t, speech });
    expect(speech.stop).toHaveBeenCalledTimes(1);
    expect(speech.calls).toEqual([{ text: t("advice.speech.no_need", {}), language }]);
  });

  it("given the module when scanning its source then no sentence is hard-coded", async () => {
    const src = require("node:fs").readFileSync(require.resolve("../adviceVoice.ts"), "utf-8");
    expect(src).not.toMatch(/["'`][^"'`]*\b(irrigate|irriguer|pluie|rain)\b[^"'`]* [^"'`]*["'`]\s*[,;)]/i);
    expect(src).toMatch(/advice\.speech\./);
  });
});
