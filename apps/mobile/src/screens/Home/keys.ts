export const HOME_TEXT_KEYS = [
  "home.title",
  "home.subtitle",
  "home.speak",
  "home.openTrialRecord",
  "home.offlineBanner",
  "home.state.empty",
  "home.state.emptyAction",
  "home.state.error",
  "home.state.errorSolution",
  "home.state.retry",
  "home.state.loading",
  "home.state.ready",
  "lang.ary",
  "lang.ary-Latn",
  "lang.ar",
  "lang.fr",
] as const;
export type HomeTextKey = (typeof HOME_TEXT_KEYS)[number];
