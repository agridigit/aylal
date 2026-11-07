import { areaM2 } from "./area";
import type { Pt } from "./area";

export type { Pt };

export const MIN_VERTICES = 3;
export const MAX_VERTICES = 500;
export const MAX_IMPORT_FEATURES = 200;
export const MAX_IMPORT_VERTICES_TOTAL = 20000;
export const MIN_AREA_M2 = 1;
export const SIMPLIFY_TOLERANCE_M = 1.5;
/** Versioned national extent (bounding box, lon/lat). */
export const MOROCCO_EXTENT = { minLon: -17.2, maxLon: -0.9, minLat: 20.7, maxLat: 36.0 } as const;

export type RingResult =
  | { ok: true; ring: Pt[]; areaHa: number }
  | { ok: false; code: "invalid_coordinates" | "too_few_vertices" | "too_many_vertices" | "area_too_small" }
  | { ok: false; code: "self_intersection"; crossings: Pt[] };

const same = (a: Pt, b: Pt) => a[0] === b[0] && a[1] === b[1];

/** Drops the closing point and consecutive duplicates. */
export function openRing(ring: readonly Pt[]): Pt[] {
  const out: Pt[] = [];
  for (const p of ring) if (!out.length || !same(out[out.length - 1] as Pt, p)) out.push([p[0], p[1]]);
  while (out.length > 1 && same(out[0] as Pt, out[out.length - 1] as Pt)) out.pop();
  return out;
}

function cross(o: Pt, a: Pt, b: Pt): number {
  return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
}

function properCrossing(a: Pt, b: Pt, c: Pt, d: Pt): Pt | null {
  const d1 = cross(a, b, c), d2 = cross(a, b, d), d3 = cross(c, d, a), d4 = cross(c, d, b);
  if (d1 * d2 < 0 && d3 * d4 < 0) {
    const t = d3 / (d3 - d4);
    return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
  }
  return null;
}

export function selfCrossings(pts: readonly Pt[]): Pt[] {
  const n = pts.length;
  const out: Pt[] = [];
  for (let i = 0; i < n; i++) {
    for (let j = i + 2; j < n; j++) {
      if (i === 0 && j === n - 1) continue;
      const x = properCrossing(pts[i] as Pt, pts[(i + 1) % n] as Pt, pts[j] as Pt, pts[(j + 1) % n] as Pt);
      if (x) out.push(x);
    }
  }
  return out;
}

export function validateRing(input: readonly Pt[]): RingResult {
  // Raw length cap before any O(n^2) work (DoS): 500 vertices plus the closing point.
  if (input.length > MAX_VERTICES + 1) return { ok: false, code: "too_many_vertices" };
  for (const p of input) {
    if (!Array.isArray(p) || p.length < 2 || !Number.isFinite(p[0]) || !Number.isFinite(p[1]) || Math.abs(p[0]) > 180 || Math.abs(p[1]) > 90) {
      return { ok: false, code: "invalid_coordinates" };
    }
  }
  const ring = openRing(input);
  const distinct = new Set(ring.map((p) => `${p[0]},${p[1]}`)).size;
  if (distinct < MIN_VERTICES) return { ok: false, code: "too_few_vertices" };
  if (distinct > MAX_VERTICES) return { ok: false, code: "too_many_vertices" };
  const crossings = selfCrossings(ring);
  if (crossings.length) return { ok: false, code: "self_intersection", crossings };
  const m2 = areaM2(ring);
  if (m2 < MIN_AREA_M2) return { ok: false, code: "area_too_small" };
  return { ok: true, ring, areaHa: m2 / 10_000 };
}

export function isInMorocco(point: readonly [number, number]): boolean {
  const [lon, lat] = point;
  const e = MOROCCO_EXTENT;
  return lon >= e.minLon && lon <= e.maxLon && lat >= e.minLat && lat <= e.maxLat;
}

export function centroid(ring: readonly Pt[]): Pt {
  const r = openRing(ring);
  return [r.reduce((s, p) => s + p[0], 0) / r.length, r.reduce((s, p) => s + p[1], 0) / r.length];
}

const M_PER_DEG = 111_194.9;

function distM(p: Pt, a: Pt, b: Pt, cosLat: number): number {
  const ax = a[0] * cosLat * M_PER_DEG, ay = a[1] * M_PER_DEG;
  const bx = b[0] * cosLat * M_PER_DEG, by = b[1] * M_PER_DEG;
  const px = p[0] * cosLat * M_PER_DEG, py = p[1] * M_PER_DEG;
  const dx = bx - ax, dy = by - ay;
  const len2 = dx * dx + dy * dy;
  if (len2 === 0) return Math.hypot(px - ax, py - ay);
  const t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / len2));
  return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
}

function douglasPeucker(pts: readonly Pt[], tol: number): Pt[] {
  if (pts.length < 3) return pts.map((p) => [p[0], p[1]] as Pt);
  const cosLat = Math.cos(((pts[0] as Pt)[1] * Math.PI) / 180);
  const keep = new Array<boolean>(pts.length).fill(false);
  keep[0] = keep[pts.length - 1] = true;
  const stack: [number, number][] = [[0, pts.length - 1]];
  while (stack.length) {
    const [s, e] = stack.pop() as [number, number];
    let max = -1, idx = -1;
    for (let i = s + 1; i < e; i++) {
      const d = distM(pts[i] as Pt, pts[s] as Pt, pts[e] as Pt, cosLat);
      if (d > max) { max = d; idx = i; }
    }
    if (idx >= 0 && max > tol) {
      keep[idx] = true;
      stack.push([s, idx], [idx, e]);
    }
  }
  return pts.filter((_, i) => keep[i]);
}

/** Douglas-Peucker at 1.5 m; the tolerance grows until at most 500 vertices remain. */
export function simplifyTrack(points: readonly Pt[], tol = SIMPLIFY_TOLERANCE_M): Pt[] {
  let t = tol;
  let out = douglasPeucker(points, t);
  while (out.length > MAX_VERTICES) {
    t *= 2;
    out = douglasPeucker(points, t);
  }
  return out;
}

export type ImportedField = { ring: Pt[]; areaHa: number; properties: Record<string, unknown> };
export type ImportResult = { valid: ImportedField[]; rejected: { index: number; reason: string }[] };

/** GeoJSON import: polygons only, MultiPolygon split, same ring validations, at most 200 entities. */
export function importFeatures(geojson: any): ImportResult {
  const entities: { index: number; ring: Pt[] | null; properties: Record<string, unknown> }[] = [];
  (geojson?.features ?? []).forEach((f: any, index: number) => {
    const g = f?.geometry;
    const properties = f?.properties ?? {};
    if (g?.type === "Polygon") entities.push({ index, ring: g.coordinates?.[0] ?? [], properties });
    else if (g?.type === "MultiPolygon") for (const poly of g.coordinates ?? []) entities.push({ index, ring: poly?.[0] ?? [], properties });
    else entities.push({ index, ring: null, properties });
  });
  if (entities.length > MAX_IMPORT_FEATURES) throw new Error("too_many_features");
  let total = 0;
  for (const e of entities) total += e.ring ? openRing(e.ring).length : 0;
  if (total > MAX_IMPORT_VERTICES_TOTAL) throw new Error("too_many_vertices_total");
  const result: ImportResult = { valid: [], rejected: [] };
  for (const e of entities) {
    if (!e.ring) { result.rejected.push({ index: e.index, reason: "not_a_polygon" }); continue; }
    const r = validateRing(e.ring);
    if (r.ok) result.valid.push({ ring: r.ring, areaHa: r.areaHa, properties: e.properties });
    else result.rejected.push({ index: e.index, reason: r.code });
  }
  return result;
}
