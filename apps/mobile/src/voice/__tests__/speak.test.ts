import { speak, speechLanguageFor } from "../speak";

const fake = () => {
  const calls: any[] = [];
  return { calls, speech: { stop: () => calls.push(["stop"]), speak: (t: string, o: any) => calls.push(["speak", t, o]) } };
};

describe("voice reading (FR-011, R13)", () => {
  it("Given the chosen language, When mapping to a device voice, Then ary and ar use Arabic and fr uses French", () => {
    expect(speechLanguageFor("ary")).toMatch(/^ar/);
    expect(speechLanguageFor("ar")).toMatch(/^ar/);
    expect(speechLanguageFor("fr")).toMatch(/^fr/);
    expect(speechLanguageFor("ary-Latn")).toBeTruthy();
  });

  it("Given a text and a language, When speaking, Then the device synthesis reads it in that language", () => {
    const { calls, speech } = fake();
    speak("Bienvenue", "fr", { speech });
    const s = calls.find((c) => c[0] === "speak");
    expect(s[1]).toBe("Bienvenue");
    expect(s[2].language).toMatch(/^fr/);
  });

  it("Given speech in progress, When speaking again, Then the previous one is stopped first", () => {
    const { calls, speech } = fake();
    speak("a", "ar", { speech });
    expect(calls.map((c) => c[0])).toEqual(["stop", "speak"]);
  });

  it("Given an empty text, When speaking, Then nothing is read", () => {
    const { calls, speech } = fake();
    speak("  ", "fr", { speech });
    expect(calls.find((c) => c[0] === "speak")).toBeUndefined();
  });
});
