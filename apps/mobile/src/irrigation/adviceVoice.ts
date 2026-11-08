import type { Locale } from "@aylal/i18n";
import { speak, type SpeechEngine } from "../voice/speak";

type T = (key: string, params?: Record<string, unknown>) => string;
export interface SpokenAdvice {
  kind: string;
  total_minutes?: number | null;
  for_date: string;
  is_last_known?: boolean;
  unavailable_reason?: string | null;
  stress_level?: string | null;
  confidence?: string;
  [extra: string]: unknown;
}

/** The sentence read aloud, built only from i18n keys (FR-020). */
export function adviceSpeech(a: SpokenAdvice, t: T): string {
  const base = (() => {
    switch (a.kind) {
      case "irrigate": {
        const total = a.total_minutes ?? 0;
        return t("advice.speech.irrigate", { hours: Math.floor(total / 60), minutes: total % 60 });
      }
      case "unavailable":
        return t("advice.speech.unavailable", { reason: a.unavailable_reason });
      case "rainfed_stress":
        return t("advice.speech.rainfed_stress", { level: a.stress_level });
      default:
        return t(`advice.speech.${a.kind}`, {});
    }
  })();
  return a.is_last_known ? `${t("advice.speech.last_known", { date: a.for_date })} ${base}` : base;
}

export function speakAdvice(a: SpokenAdvice, locale: Locale, deps: { t: T; speech?: SpeechEngine }): void {
  speak(adviceSpeech(a, deps.t), locale, { speech: deps.speech });
}
