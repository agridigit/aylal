type Row = { parcel_id: string; volume_m3: number; area_ha: number | null };

/** R4: volume and volume per hectare per parcel (null without a surface), total, and the empty state. Aggregate only: no author, no note. */
export function summariseConsumption(i: { parcels: Row[] }): {
  parcels: any[]; total_m3: number; empty: boolean;
} {
  const parcels = i.parcels.map((p) => ({
    parcel_id: p.parcel_id, volume_m3: p.volume_m3,
    volume_m3_per_ha: typeof p.area_ha === "number" && p.area_ha > 0 ? p.volume_m3 / p.area_ha : null,
  }));
  const total = parcels.reduce((s, p) => s + p.volume_m3, 0);
  return { parcels, total_m3: total, empty: total === 0 };
}
