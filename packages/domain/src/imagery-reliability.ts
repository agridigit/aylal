/** Imagery is low reliability on a small parcel or under a greenhouse (FR-009). */
export function imageryReliability(parcel: { areaHa: number; greenhouse: boolean }, minAreaHa: number): "ok" | "low" {
  return parcel.greenhouse || parcel.areaHa < minAreaHa ? "low" : "ok";
}
