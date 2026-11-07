import { areaM2 } from "./area";
import { openRing } from "./geometry";
import type { Pt } from "./area";

const M_PER_DEG = 111_194.9;
export const OVERLAP_WARN_RATIO = 0.01;
const TOUCH_EPS_M = 0.05;

function project(ring: readonly Pt[], lon0: number, lat0: number): Pt[] {
  const c = Math.cos((lat0 * Math.PI) / 180);
  return openRing(ring).map(([x, y]) => [(x - lon0) * c * M_PER_DEG, (y - lat0) * M_PER_DEG] as Pt);
}

const signed = (p: Pt[]) => p.reduce((s, a, i) => { const b = p[(i + 1) % p.length]; return s + (a[0] * b[1] - b[0] * a[1]); }, 0) / 2;
const cr = (o: Pt, a: Pt, b: Pt) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);

function triangulate(poly: Pt[]): Pt[][] {
  const p = signed(poly) < 0 ? [...poly].reverse() : [...poly];
  const tris: Pt[][] = [];
  let guard = p.length * p.length + 10;
  while (p.length > 3 && guard-- > 0) {
    let clipped = false;
    for (let i = 0; i < p.length; i++) {
      const a = p[(i + p.length - 1) % p.length], b = p[i], c = p[(i + 1) % p.length];
      if (cr(a, b, c) <= 0) continue;
      const inside = p.some((q) => q !== a && q !== b && q !== c && cr(a, b, q) >= 0 && cr(b, c, q) >= 0 && cr(c, a, q) >= 0);
      if (inside) continue;
      tris.push([a, b, c]);
      p.splice(i, 1);
      clipped = true;
      break;
    }
    if (!clipped) p.splice(0, 1); // degenerate remainder
  }
  if (p.length === 3) tris.push([p[0], p[1], p[2]]);
  return tris;
}

/** Sutherland-Hodgman against a convex counter-clockwise clip polygon. */
function clipConvex(subject: Pt[], clip: Pt[]): Pt[] {
  let out = subject;
  for (let i = 0; i < clip.length && out.length; i++) {
    const a = clip[i], b = clip[(i + 1) % clip.length];
    const input = out;
    out = [];
    for (let j = 0; j < input.length; j++) {
      const cur = input[j], prev = input[(j + input.length - 1) % input.length];
      const dc = cr(a, b, cur), dp = cr(a, b, prev);
      if (dc >= 0) {
        if (dp < 0) out.push(inter(prev, cur, dp, dc));
        out.push(cur);
      } else if (dp >= 0) out.push(inter(prev, cur, dp, dc));
    }
  }
  return out;
}
const inter = (p: Pt, q: Pt, dp: number, dc: number): Pt => { const t = dp / (dp - dc); return [p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t]; };

function localFrame(a: readonly Pt[]): [number, number] {
  const p = openRing(a);
  return [p[0][0], p[0][1]];
}

/** Intersection area (m2) of two lon/lat rings. */
export function intersectionAreaM2(a: readonly Pt[], b: readonly Pt[]): number {
  const [lon0, lat0] = localFrame(a);
  const pa = project(a, lon0, lat0), pb = project(b, lon0, lat0);
  const subject = signed(pa) < 0 ? [...pa].reverse() : pa;
  let total = 0;
  for (const tri of triangulate(pb)) total += Math.abs(signed(clipConvex(subject, tri)));
  return total;
}

/** True when the rings share at least a boundary point (within 5 cm) or overlap. */
export function ringsTouch(a: readonly Pt[], b: readonly Pt[]): boolean {
  const [lon0, lat0] = localFrame(a);
  const pa = project(a, lon0, lat0), pb = project(b, lon0, lat0);
  const segDist = (p: Pt, s: Pt, e: Pt) => {
    const dx = e[0] - s[0], dy = e[1] - s[1], l2 = dx * dx + dy * dy;
    const t = l2 === 0 ? 0 : Math.max(0, Math.min(1, ((p[0] - s[0]) * dx + (p[1] - s[1]) * dy) / l2));
    return Math.hypot(p[0] - s[0] - t * dx, p[1] - s[1] - t * dy);
  };
  for (const [P, Q] of [[pa, pb], [pb, pa]] as [Pt[], Pt[]][])
    for (const p of P) for (let j = 0; j < Q.length; j++) if (segDist(p, Q[j], Q[(j + 1) % Q.length]) <= TOUCH_EPS_M) return true;
  for (let i = 0; i < pa.length; i++) for (let j = 0; j < pb.length; j++) {
    const s = pa[i], e = pa[(i + 1) % pa.length], c = pb[j], d = pb[(j + 1) % pb.length];
    if (cr(s, e, c) * cr(s, e, d) < 0 && cr(c, d, s) * cr(c, d, e) < 0) return true;
  }
  return intersectionAreaM2(a, b) > 0;
}

/** Ids of the other fields overlapping by more than 1 percent of the smaller area (never blocking). */
export function overlapWarnings(ring: readonly Pt[], others: readonly { id: string; ring: readonly Pt[] }[]): string[] {
  const mine = areaM2(ring);
  return others
    .filter((o) => intersectionAreaM2(ring, o.ring) > OVERLAP_WARN_RATIO * Math.min(mine, areaM2(o.ring)))
    .map((o) => o.id);
}
