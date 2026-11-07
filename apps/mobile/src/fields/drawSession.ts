import { areaHa } from "@aylal/domain/area";
import { MAX_VERTICES, centroid, isInMorocco, validateRing } from "@aylal/domain/geometry";
import type { Pt } from "@aylal/domain/geometry";

export type DrawResult =
  | { ok: true; ring: Pt[]; areaHa: number }
  | { ok: false; code: string; crossings?: Pt[] };

/** Validates drawn points (taps or simplified GPS track) with the shared domain rules. */
export function validateDrawn(points: readonly Pt[]): DrawResult {
  if (points.length < 3) return { ok: false, code: "too_few_points" };
  const r = validateRing(points);
  if (!r.ok) {
    if (r.code === "too_few_vertices") return { ok: false, code: "too_few_points" };
    return r.code === "self_intersection" ? { ok: false, code: r.code, crossings: r.crossings } : { ok: false, code: r.code };
  }
  if (!isInMorocco(centroid(r.ring))) return { ok: false, code: "outside_morocco" };
  const first = r.ring[0] as Pt;
  return { ok: true, ring: [...r.ring, [first[0], first[1]]], areaHa: areaHa(r.ring) };
}

export function createDrawSession(_opts: { mode: "taps" | "gps" }) {
  let pts: Pt[] = [];
  return {
    addPoint(p: Pt) {
      if (pts.length >= MAX_VERTICES) throw new Error("too_many_vertices");
      pts.push([p[0], p[1]]);
    },
    undo() {
      pts.pop();
    },
    movePoint(index: number, p: Pt) {
      if (index >= 0 && index < pts.length) pts[index] = [p[0], p[1]];
    },
    points: () => pts.map((p) => [p[0], p[1]] as Pt),
    validate: () => validateDrawn(pts),
    reset() {
      pts = [];
    },
  };
}
