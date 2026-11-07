import { isRtl, type Locale } from "@aylal/i18n";

export const MIN_TOUCH_TARGET_DP = 48;

export interface RtlManager {
  isRTL: boolean;
  allowRTL(v: boolean): void;
  forceRTL(v: boolean): void;
}

export function layoutFor(locale: Locale) {
  const rtl = isRtl(locale);
  return {
    isRTL: rtl,
    writingDirection: rtl ? ("rtl" as const) : ("ltr" as const),
    textAlign: rtl ? ("right" as const) : ("left" as const),
    mirrorIcons: rtl,
  };
}

/** Applies the locale direction; a reload is required when the runtime direction differs. */
export function applyLocaleDirection(locale: Locale, manager: RtlManager) {
  const rtl = isRtl(locale);
  manager.allowRTL(true);
  manager.forceRTL(rtl);
  return { isRTL: rtl, reloadRequired: manager.isRTL !== rtl };
}

const MIRROR: Record<string, string> = { "chevron-forward": "chevron-back", "chevron-back": "chevron-forward" };

export function directionalIcon(name: string, rtl: boolean): string {
  return rtl ? (MIRROR[name] ?? name) : name;
}
