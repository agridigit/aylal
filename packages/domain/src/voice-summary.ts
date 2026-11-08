export interface SummaryParcel {
  parcel_id: string;
  color: string;
  reason_key: string;
}

/** Red parcels first, then orange (stable inside a colour); green ones have nothing to read. */
export function orderSummary<T extends SummaryParcel>(parcels: readonly T[]): T[] {
  return [...parcels.filter((p) => p.color === "red"), ...parcels.filter((p) => p.color === "orange")];
}
