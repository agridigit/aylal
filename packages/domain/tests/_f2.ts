import { readFileSync } from "node:fs";

export type Pt = [number, number];

export function vectors<T = any>(name: string): T[] {
  return JSON.parse(readFileSync(new URL(`../vectors/${name}`, import.meta.url), "utf-8"));
}

export function square(lon: number, lat: number, size: number): Pt[] {
  return [[lon, lat], [lon + size, lat], [lon + size, lat + size], [lon, lat + size], [lon, lat]];
}

/** Regular polygon with n distinct vertices (not closed), radius in degrees. */
export function polygon(n: number, lon = -7.6, lat = 33.57, r = 0.01): Pt[] {
  return Array.from({ length: n }, (_, i) => [lon + r * Math.cos((2 * Math.PI * i) / n), lat + r * Math.sin((2 * Math.PI * i) / n)] as Pt);
}
