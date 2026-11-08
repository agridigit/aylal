import { createVoiceSummary } from "../voiceSummary";

const items = [
  { parcel_id: "o1", color: "orange", reason_key: "status.watch" },
  { parcel_id: "r1", color: "red", reason_key: "status.frost" },
];
const summary = (locale: string) => ({ summary_date: "2026-12-05", locale, items, weather_code: "sun" });
const translate = (key: string, params?: Record<string, string>) => `[${key}${params?.parcel ? `:${params.parcel}` : ""}]`;

function fakeSpeech(voices: { identifier: string; language: string }[]) {
  const spoken: { text: string; language?: string }[] = [];
  return {
    spoken,
    engine: {
      getAvailableVoicesAsync: async () => voices,
      speak: (text: string, o: { language?: string; onDone?: () => void }) => { spoken.push({ text, language: o.language }); o.onDone?.(); },
      stop: jest.fn(),
    },
  };
}

describe("voice summary playback on the device (R7-A1, R7-A2, R7-A3)", () => {
  it("given a darija summary and a Moroccan Arabic voice then it is read with that voice, red parcels first", async () => {
    const s = fakeSpeech([{ identifier: "a", language: "ar-MA" }, { identifier: "b", language: "ar-SA" }]);
    const out = await createVoiceSummary({ speech: s.engine, translate }).play(summary("ary"));
    expect(out).toEqual({ mode: "voice", language: "ar-MA" });
    const text = s.spoken[0]?.text ?? "";
    expect(text.indexOf("[summary.red")).toBeGreaterThanOrEqual(0);
    expect(text.indexOf("[summary.red")).toBeLessThan(text.indexOf("[summary.orange"));
    expect(text.indexOf("[summary.orange")).toBeLessThan(text.indexOf("[summary.weather"));
  });

  it("given a darija summary and no darija voice then an Arabic voice is used", async () => {
    const s = fakeSpeech([{ identifier: "b", language: "ar-SA" }, { identifier: "c", language: "fr-FR" }]);
    expect(await createVoiceSummary({ speech: s.engine, translate }).play(summary("ary"))).toEqual({ mode: "voice", language: "ar-SA" });
  });

  it("given a darija summary and no Arabic voice at all then the text is shown instead of being spoken", async () => {
    const s = fakeSpeech([{ identifier: "c", language: "fr-FR" }]);
    const out = await createVoiceSummary({ speech: s.engine, translate }).play(summary("ary"));
    expect(out.mode).toBe("text");
    expect(s.spoken).toHaveLength(0);
    if (out.mode === "text") expect(out.text).toContain("[summary.red");
  });

  it("given a French summary then only a French voice is used", async () => {
    const s = fakeSpeech([{ identifier: "b", language: "ar-SA" }, { identifier: "c", language: "fr-FR" }]);
    expect(await createVoiceSummary({ speech: s.engine, translate }).play(summary("fr"))).toEqual({ mode: "voice", language: "fr-FR" });
  });

  it("given an Arabic summary and no Arabic voice then the text is shown", async () => {
    const s = fakeSpeech([{ identifier: "c", language: "fr-FR" }]);
    expect((await createVoiceSummary({ speech: s.engine, translate }).play(summary("ar"))).mode).toBe("text");
  });

  it("given a speech engine that fails then the text is shown instead of an error", async () => {
    const engine = { getAvailableVoicesAsync: async () => [{ identifier: "c", language: "fr-FR" }], speak: () => { throw new Error("tts"); }, stop: jest.fn() };
    expect((await createVoiceSummary({ speech: engine, translate }).play(summary("fr"))).mode).toBe("text");
  });

  it("given no network then an already received summary is still read, with no network call", async () => {
    const fetchSpy = jest.fn();
    (globalThis as any).fetch = fetchSpy;
    const s = fakeSpeech([{ identifier: "c", language: "fr-FR" }]);
    expect((await createVoiceSummary({ speech: s.engine, translate }).play(summary("fr"))).mode).toBe("voice");
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("given a summary with no parcel to watch then the spoken text says so instead of being silent", async () => {
    const s = fakeSpeech([{ identifier: "c", language: "fr-FR" }]);
    await createVoiceSummary({ speech: s.engine, translate }).play({ ...summary("fr"), items: [] });
    expect(s.spoken[0]?.text).toContain("[summary.nothing_to_watch]");
  });

  it("given a summary playing then stop silences the engine", async () => {
    const s = fakeSpeech([{ identifier: "c", language: "fr-FR" }]);
    createVoiceSummary({ speech: s.engine, translate }).stop();
    expect(s.engine.stop).toHaveBeenCalledTimes(1);
  });
});
