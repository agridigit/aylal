export type Pt = [number, number];

/** Authalic Earth radius (m). */
export const AUTHALIC_RADIUS_M = 6371007.2;

const rad = (d: number) => (d * Math.PI) / 180;

/** Geodesic area in m2 of a lon/lat ring on the authalic sphere (spherical polygon, any winding). */
export function areaM2(ring: readonly Pt[]): number {
  const n = ring.length;
  if (n < 3) return 0;
  let sum = 0;
  for (let i = 0; i < n; i++) {
    const [lon1, lat1] = ring[i];
    const [lon2, lat2] = ring[(i + 1) % n];
    sum += rad(lon2 - lon1) * (2 + Math.sin(rad(lat1)) + Math.sin(rad(lat2)));
  }
  return (Math.abs(sum) * AUTHALIC_RADIUS_M * AUTHALIC_RADIUS_M) / 2;
}

export function areaHa(ring: readonly Pt[]): number {
  return areaM2(ring) / 10_000;
}

/** Hectares shown to the farmer: 2 decimals. */
export function displayAreaHa(ha: number): number {
  return Math.round((ha + Number.EPSILON) * 100) / 100;
}
