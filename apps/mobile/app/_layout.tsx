import { Slot } from "expo-router";
import { ThemeProvider } from "@aylal/ui";
import { isRtl, type Locale } from "@aylal/i18n";
import { createContext, useContext, useState, type ReactNode } from "react";
import { I18nManager } from "react-native";
import { createI18n, DEFAULT_LOCALE, type I18n } from "@aylal/i18n";
import { startupMark } from "../src/screens/Home/Home";

startupMark.appStarted();

interface LocaleCtx {
  i18n: I18n;
  setLocale: (l: Locale) => void;
}
const Ctx = createContext<LocaleCtx | null>(null);
export const useLocale = () => useContext(Ctx) as LocaleCtx;

export default function RootLayout(): ReactNode {
  const [i18n, setI18n] = useState<I18n>(() => createI18n(DEFAULT_LOCALE));
  const setLocale = (l: Locale) => {
    const next = createI18n(l);
    I18nManager.forceRTL(isRtl(next.locale));
    setI18n(next);
  };
  return (
    <Ctx.Provider value={{ i18n, setLocale }}>
      <ThemeProvider name="light" direction={isRtl(i18n.locale) ? "rtl" : "ltr"}>
        <Slot />
      </ThemeProvider>
    </Ctx.Provider>
  );
}
