import { composeSummary } from "@aylal/domain/voice-summary";

export interface SpeechVoice {
  identifier: string;
  language: string;
}

export interface SpeechEngine {
  getAvailableVoicesAsync: () => Promise<SpeechVoice[]>;
  speak: (text: string, options: { language?: string; voice?: string; onDone?: () => void; onError?: (e: unknown) => void }) => void;
  stop: () => void | Promise<void>;
}

export interface DailySummary {
  summary_date: string;
  locale: string;
  items: { parcel_id: string; color: string; reason_key: string }[];
  weather_code: string | null;
}

export type PlayOutcome = { mode: "voice"; language: string } | { mode: "text"; text: string };

type Translate = (key: string, params?: Record<string, string>) => string;

function pickVoice(voices: readonly SpeechVoice[], locale: string): SpeechVoice | undefined {
  const lang = (v: SpeechVoice) => v.language.replace("_", "-").toLowerCase();
  if (locale === "ary") return voices.find((v) => lang(v) === "ar-ma") ?? voices.find((v) => lang(v).startsWith("ar"));
  if (locale === "ar") return voices.find((v) => lang(v).startsWith("ar"));
  return voices.find((v) => lang(v).startsWith("fr"));
}

/** Local text-to-speech of a summary already received: no network, text fallback when no voice or engine failure. */
export function createVoiceSummary(deps: { speech: SpeechEngine; translate: Translate }) {
  const compose = (s: DailySummary): string => {
    const composed = composeSummary({
      items: s.items,
      weatherCode: s.weather_code,
      locale: s.locale,
      visibleParcelIds: s.items.map((i) => i.parcel_id),
    });
    return composed.segments
      .map((seg) => {
        const params: Record<string, string> = {};
        if (seg.parcelId) params.parcel = seg.parcelId;
        if (seg.reasonKey) params.reason = deps.translate(seg.reasonKey);
        if (seg.weatherCode) params.weather = deps.translate(`weather.${seg.weatherCode}`);
        return deps.translate(seg.key, params);
      })
      .join(". ");
  };
  return {
    async play(summary: DailySummary): Promise<PlayOutcome> {
      const text = compose(summary);
      try {
        const locale = summary.locale === "ary" || summary.locale === "ar" ? summary.locale : "fr";
        const voice = pickVoice(await deps.speech.getAvailableVoicesAsync(), locale);
        if (!voice) return { mode: "text", text };
        deps.speech.speak(text, { language: voice.language, voice: voice.identifier });
        return { mode: "voice", language: voice.language };
      } catch {
        return { mode: "text", text };
      }
    },
    stop(): void {
      void deps.speech.stop();
    },
  };
}
