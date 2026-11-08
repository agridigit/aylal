export interface SummaryParcel {
  parcel_id: string;
  color: string;
  reason_key: string;
}

/** Red parcels first, then orange (stable inside a colour); green ones have nothing to read. */
export function orderSummary<T extends SummaryParcel>(parcels: readonly T[]): T[] {
  return [...parcels.filter((p) => p.color === "red"), ...parcels.filter((p) => p.color === "orange")];
}

export type SummaryLocale = "ary" | "ar" | "fr";

export interface SummarySegment {
  key: string;
  parcelId?: string;
  reasonKey?: string;
  weatherCode?: string;
}

export interface ComposedSummary {
  locale: SummaryLocale;
  segments: SummarySegment[];
}

/** i18n keys only: red parcels, then orange, then the weather; a parcel outside the recipient scope is never cited. */
export function composeSummary(input: {
  items: readonly SummaryParcel[];
  weatherCode: string | null;
  locale: string;
  visibleParcelIds: readonly string[];
}): ComposedSummary {
  const locale: SummaryLocale = input.locale === "ary" || input.locale === "ar" ? input.locale : "fr";
  const visible = new Set(input.visibleParcelIds);
  const ordered = orderSummary(input.items.filter((p) => visible.has(p.parcel_id)));
  const segments: SummarySegment[] = [{ key: "summary.intro" }];
  if (ordered.length === 0) segments.push({ key: "summary.nothing_to_watch" });
  for (const p of ordered) segments.push({ key: p.color === "red" ? "summary.red" : "summary.orange", parcelId: p.parcel_id, reasonKey: p.reason_key });
  segments.push(input.weatherCode ? { key: "summary.weather", weatherCode: input.weatherCode } : { key: "summary.weather_unavailable" });
  return { locale, segments };
}
