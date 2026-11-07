import ary from "../locales/ary.json";
import aryLatn from "../locales/ary-Latn.json";
import ar from "../locales/ar.json";
import fr from "../locales/fr.json";

export const LOCALES = ["ary", "ary-Latn", "ar", "fr"] as const;
export type Locale = (typeof LOCALES)[number];
export type Resource = { [key: string]: string | Resource };

export const DEFAULT_LOCALE: Locale = "fr";
const RTL: readonly Locale[] = ["ary", "ar"];

export const resources: Record<Locale, Resource> = { ary, "ary-Latn": aryLatn, ar, fr };

/** Flatten a nested resource to dotted keys. */
export function flattenKeys(res: Resource, prefix = ""): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(res)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (typeof v === "string") out[key] = v;
    else Object.assign(out, flattenKeys(v, key));
  }
  return out;
}

/** Throws naming each locale and key that is missing or empty compared with the reference locale. */
export function assertComplete(all: Record<string, Resource>, reference: string = DEFAULT_LOCALE): void {
  const ref = all[reference];
  if (!ref) throw new Error(`i18n: reference locale ${reference} not found`);
  const refKeys = Object.keys(flattenKeys(ref));
  const problems: string[] = [];
  for (const [locale, res] of Object.entries(all)) {
    const flat = flattenKeys(res);
    for (const k of refKeys) {
      if (!(k in flat)) problems.push(`${locale}: missing ${k}`);
      else if (!flat[k]?.trim()) problems.push(`${locale}: empty ${k}`);
    }
  }
  if (problems.length) throw new Error(`i18n incomplete: ${problems.join("; ")}`);
}

/** Maps a device language tag to a supported locale; falls back to fr. */
export function resolveLocale(tag: string | undefined | null): Locale {
  if (!tag) return DEFAULT_LOCALE;
  const exact = LOCALES.find((l) => l.toLowerCase() === tag.toLowerCase());
  if (exact) return exact;
  const base = tag.toLowerCase().split(/[-_]/)[0];
  if (base === "ary") return "ary";
  return LOCALES.find((l) => l === base) ?? DEFAULT_LOCALE;
}

export function isRtl(locale: Locale): boolean {
  return RTL.includes(locale);
}

export interface I18n {
  readonly locale: Locale;
  t(key: string, vars?: Record<string, string | number>): string;
  changeLanguage(locale: string): Promise<void>;
}

export function createI18n(initial: string | undefined = DEFAULT_LOCALE): I18n {
  let locale = resolveLocale(initial);
  let flat = flattenKeys(resources[locale]);
  return {
    get locale() {
      return locale;
    },
    t(key, vars) {
      const value = flat[key];
      if (value === undefined) return key;
      return value.replace(/\{\{\s*(\w+)\s*\}\}/g, (m, n: string) => (vars && n in vars ? String(vars[n]) : m));
    },
    async changeLanguage(next) {
      locale = resolveLocale(next);
      flat = flattenKeys(resources[locale]);
    },
  };
}

export const LANGUAGE_CODES = ["ary", "ar", "fr"] as const;
export type LanguageCode = (typeof LANGUAGE_CODES)[number];

export interface LanguageOption {
  code: LanguageCode;
  label: string;
  spokenText: string;
  speechLocale: string;
  dir: "rtl" | "ltr";
}

/** First-launch choice, in display order; each label and spoken text is in its own language. */
export const LANGUAGE_OPTIONS: readonly LanguageOption[] = [
  { code: "ary", label: "الدارجة", spokenText: "الدارجة المغربية", speechLocale: "ar-MA", dir: "rtl" },
  { code: "ar", label: "العربية", spokenText: "اللغة العربية", speechLocale: "ar", dir: "rtl" },
  { code: "fr", label: "Français", spokenText: "Français", speechLocale: "fr-FR", dir: "ltr" },
];

/** Switches texts and direction at once; refuses an unknown language and keeps the current one. */
export async function applyLanguage(i18n: I18n, code: string): Promise<{ locale: Locale; rtl: boolean }> {
  if (!LANGUAGE_OPTIONS.some((o) => o.code === code)) throw new Error(`i18n: unsupported language ${code}`);
  await i18n.changeLanguage(code);
  return { locale: i18n.locale, rtl: isRtl(i18n.locale) };
}
