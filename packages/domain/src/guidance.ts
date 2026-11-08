export interface LatLon {
  lat: number;
  lon: number;
}

const EARTH_RADIUS_M = 6_371_000;
const rad = (d: number) => (d * Math.PI) / 180;

/** Straight-line heading (degrees from north, [0, 360)) and distance (metres) from a point to a target. */
export function guidance(from: LatLon, to: LatLon): { bearingDeg: number; distanceM: number } {
  const p1 = rad(from.lat);
  const p2 = rad(to.lat);
  const dp = p2 - p1;
  const dl = rad(to.lon - from.lon);
  const a = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  const distanceM = 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(a)));
  if (distanceM === 0) return { bearingDeg: 0, distanceM: 0 };
  const y = Math.sin(dl) * Math.cos(p2);
  const x = Math.cos(p1) * Math.sin(p2) - Math.sin(p1) * Math.cos(p2) * Math.cos(dl);
  const bearingDeg = ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
  return { bearingDeg, distanceM };
}
