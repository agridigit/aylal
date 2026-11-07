const RTL_LOCALES = new Set(["ar", "ary"]);

export interface TextLayout {
  direction: "ltr" | "rtl";
  textAlign: "start";
  fontFamily: string;
  wrap: boolean;
  shrinkable: boolean;
  maxLines: number | null;
  ellipsizeMode: "tail";
}

/** Mise en page sûre : retour à la ligne, jamais coupé sur une ligne, alignement au début selon le sens. */
export function resolveTextLayout(opts: { text: string; locale: string }): TextLayout {
  const rtl = RTL_LOCALES.has(opts.locale);
  return {
    direction: rtl ? "rtl" : "ltr",
    textAlign: "start",
    fontFamily: rtl ? "IBM Plex Sans Arabic" : "IBM Plex Sans",
    wrap: true,
    shrinkable: true,
    maxLines: null,
    ellipsizeMode: "tail",
  };
}
