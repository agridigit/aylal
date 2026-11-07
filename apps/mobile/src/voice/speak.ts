import type { Locale } from "@aylal/i18n";

export interface SpeechEngine {
  stop(): void;
  speak(text: string, options: { language: string }): void;
}

const LANGUAGES: Record<Locale, string> = { ary: "ar-MA", ar: "ar", "ary-Latn": "fr-FR", fr: "fr-FR" };

export function speechLanguageFor(locale: Locale): string {
  return LANGUAGES[locale];
}

/** Reads a text aloud with the device synthesis, stopping any previous reading first. */
export function speak(text: string, locale: Locale, deps: { speech?: SpeechEngine } = {}): void {
  if (!text.trim()) return;
  const speech: SpeechEngine = deps.speech ?? (require("expo-speech") as SpeechEngine);
  speech.stop();
  speech.speak(text, { language: speechLanguageFor(locale) });
}
