import { dark } from "./dark";
import { light } from "./light";
import { sun } from "./sun";

export const tokens = {
  themes: { light, dark, sun },
  space: { xs: 4, sm: 8, md: 16, lg: 24, xl: 32 },
  radius: { sm: 4, md: 8, lg: 16, pill: 999 },
  shadow: {
    none: "none",
    sm: "0 1px 2px rgba(0,0,0,0.20)",
    md: "0 4px 8px rgba(0,0,0,0.25)",
  },
  typography: {
    fontFamily: "IBM Plex Sans",
    fontFamilyArabic: "IBM Plex Sans Arabic",
    scale: { caption: 14, body: 18, heading: 24, title: 32 },
  },
  motion: { base: 250 },
  states: { disabledOpacity: 0.4, activeOpacity: 0.85 },
  touchTargetMin: 48,
} as const;

export type ThemeName = keyof typeof tokens.themes;
export type Theme = (typeof tokens.themes)[ThemeName];
