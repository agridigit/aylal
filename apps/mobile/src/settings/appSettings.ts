import { LOCALES, resolveLocale, type Locale } from "@aylal/i18n";

export const THEMES = ["light", "dark", "sun", "system"] as const;
export type ThemeSetting = (typeof THEMES)[number];

/** Port over the local `app_settings` table (key text PK, value text). */
export interface KeyValueStore {
  get(key: string): Promise<string | null>;
  set(key: string, value: string): Promise<void>;
}

export function createAppSettings(store: KeyValueStore) {
  return {
    async getLocale(deviceTag?: string): Promise<Locale> {
      const v = await store.get("locale");
      return (LOCALES as readonly string[]).includes(v ?? "") ? (v as Locale) : resolveLocale(deviceTag);
    },
    setLocale: (locale: Locale) => store.set("locale", locale),
    async getTheme(): Promise<ThemeSetting> {
      const v = await store.get("theme");
      return (THEMES as readonly string[]).includes(v ?? "") ? (v as ThemeSetting) : "system";
    },
    setTheme: (theme: ThemeSetting) => store.set("theme", theme),
  };
}
