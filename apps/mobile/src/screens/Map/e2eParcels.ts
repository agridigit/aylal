import type { CachedParcel } from "./mapViewModel";

// Same grid as services/api/app/db/seed.py (50 parcels); stands for the local cache in E2E builds only.
const ORIGIN_LON = -8.0;
const ORIGIN_LAT = 31.63;
const STEP = 0.002;

export function e2eParcels(): CachedParcel[] {
  return Array.from({ length: 50 }, (_, i) => {
    const lon = ORIGIN_LON + (i % 10) * STEP;
    const lat = ORIGIN_LAT + Math.floor(i / 10) * STEP;
    const w = STEP * 0.8;
    return {
      id: `e2e-parcel-${i}`,
      name: `Parcel ${String(i + 1).padStart(2, "0")}`,
      geometry: { type: "Polygon", coordinates: [[[lon, lat], [lon + w, lat], [lon + w, lat + w], [lon, lat + w], [lon, lat]]] },
      vigor: ((i * 37) % 101) / 100,
    };
  });
}
